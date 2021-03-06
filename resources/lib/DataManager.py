import hashlib
import os
import threading
import json as json

import xbmcplugin
import xbmcgui
import xbmcaddon
import xbmc

import illicoweb

# *** Thank you MediaBrowser for such a neat implementation

class DataManager():

    cacheDataResult = None
    dataUrl = None
    cacheDataPath = None
    canRefreshNow = False
    
    def remove_dynamic_info(self, d):
        if not isinstance(d, (dict, list)):
            return d
        if isinstance(d, list):
            return type(d)(self.remove_dynamic_info(v) for v in d)
        return type(d)((k,self.remove_dynamic_info(v))
            for k, v in d.items() if k not in 'orderable')
        
    def getCacheValidatorFromData(self, result):
        if(result == None):
            result = []
        
        # hash the data
        jsonData = self.remove_dynamic_info(result)    
        validatorString = hashlib.md5(json.dumps(jsonData['body']['main'])).hexdigest()
        
        #xbmc.log("Cache_Data_Manager: getCacheValidatorFromData : RawData  : " + dataHashString)
        illicoweb.addon_log("Cache_Data_Manager: getCacheValidatorFromData : hashData : " + validatorString)
        
        return validatorString

    def loadJsonData(self, jsonData):
        return json.loads(jsonData)        
        
    def GetContent(self, url, forceCache=False):
    
        #  first get the url hash
        m = hashlib.md5()
        m.update(url)
        urlHash = m.hexdigest()
        
        # build cache data path
        __addon__ = xbmcaddon.Addon(id='plugin.video.illicoweb')
        __addondir__ = xbmc.translatePath( __addon__.getAddonInfo('profile').decode('utf-8') )
        if not os.path.exists(os.path.join(__addondir__, "cache")):
            os.makedirs(os.path.join(__addondir__, "cache"))
        cacheDataPath = os.path.join(__addondir__, "cache", urlHash)
        
        illicoweb.addon_log("Cache_Data_Manager: Requested URL (%s)" % url)
        illicoweb.addon_log("Cache_Data_Manager: " + cacheDataPath)
        
        # are we forcing a reload
        WINDOW = xbmcgui.Window( 10000 )
        force_data_reload = WINDOW.getProperty("force_data_reload")
        WINDOW.setProperty("force_data_reload", "false")
    
        if(os.path.exists(cacheDataPath)) and force_data_reload != "true":
            # load data from cache if it is available and trigger a background
            # verification process to test cache validity        
            illicoweb.addon_log("Cache_Data_Manager: Loading Cached File")
            cachedfie = open(cacheDataPath, 'r')
            jsonData = cachedfie.read()
            cachedfie.close()
            try:
                result = self.loadJsonData(jsonData)

                if forceCache != True:
                    # start a worker thread to process the cache validity
                    self.cacheDataResult = result
                    self.dataUrl = url
                    self.cacheDataPath = cacheDataPath
                    actionThread = CacheManagerThread()
                    actionThread.setCacheData(self, self.cacheDataResult, self.dataUrl, self.cacheDataPath)
                    actionThread.start()
                else:
                    illicoweb.addon_log("Cache_Data_Manager: Cache copy forced.")

                illicoweb.addon_log("Cache_Data_Manager: Returning Cached Result")
                return result
            except:
                illicoweb.addon_log("Cache_Data_Manager: Corrupt cache")
                

        # no cache data so load the url and save it
        jsonData, result = illicoweb.getRequest(url)
        illicoweb.addon_log("Cache_Data_Manager: Loading URL and saving to cache")
        cachedfie = open(cacheDataPath, 'w')
        cachedfie.write(jsonData.encode('utf-8'))
        cachedfie.close()
        result = self.loadJsonData(jsonData)
        self.cacheManagerFinished = True
        illicoweb.addon_log("Cache_Data_Manager: Returning Loaded Result")        
        return result        
        
    
class CacheManagerThread(threading.Thread):

    dataManager = None
    cacheDataResult = None
    dataUrl = None
    cacheDataPath = None
    
    def setCacheData(self, data, cache, dataUrl, cacheDataPath):
        self.dataManager = data
        self.cacheDataResult = cache
        self.dataUrl = dataUrl
        self.cacheDataPath = cacheDataPath
    
    def run(self):
    
        illicoweb.addon_log("Cache_Data_Manager: CacheManagerThread Started")
        
        cacheValidatorString = self.dataManager.getCacheValidatorFromData(self.cacheDataResult)
        illicoweb.addon_log("Cache_Data_Manager: Cache Validator String (" + cacheValidatorString + ")")
        
        jsonData, result = illicoweb.getRequest(self.dataUrl)
        loadedResult = self.dataManager.loadJsonData(jsonData)
        loadedValidatorString = self.dataManager.getCacheValidatorFromData(loadedResult)
        illicoweb.addon_log("Cache_Data_Manager: loaded Validator String (" + loadedValidatorString + ")")
        
        # if they dont match then save the data and trigger a content reload
        if(cacheValidatorString != loadedValidatorString):
            illicoweb.addon_log("Cache_Data_Manager: CacheManagerThread Saving new cache data and reloading container (%s != %s)" % (cacheValidatorString, loadedValidatorString))
            cachedfie = open(self.cacheDataPath, 'w')
            cachedfie.write(jsonData.encode('utf-8'))
            cachedfie.close()

            # we need to refresh but will wait until the main function has finished
            loops = 0
            while(self.dataManager.canRefreshNow == False and loops < 200):
                xbmc.sleep(100)
                loops = loops + 1
            
            illicoweb.addon_log("Cache_Data_Manager: Sending container refresh (" + str(loops) + ")")
            xbmc.executebuiltin("Container.Refresh")

        illicoweb.addon_log("Cache_Data_Manager: CacheManagerThread Exited")