from base64 import b64encode, b64decode
from bs4 import BeautifulSoup
from threading import Thread
from uuid import uuid4
import datetime, hashlib, hmac, platform, requests, sys, time, tzlocal, urllib, xmltodict
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs


__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
data_dir = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

base_url = sys.argv[0]
__addon_handle__ = int(sys.argv[1])
args = urllib.parse.parse_qs(sys.argv[2][1:])
lang = "de" if xbmc.getLanguage(xbmc.ISO_639_1) == "de" else "en"

xbmcplugin.setContent(__addon_handle__, 'videos')

# TIME ZONE
local_timezone = tzlocal.get_localzone()

# DEFAULT HEADER
header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"}

# EPG CONTENT
def get_image(list_item):
    if list_item and len(list_item) > 0:
        resolutions = ["1920", "1440", "1280", "960", "720", "480", "360", "180"]
        for resolution in resolutions:
            for image in list_item:
                if image.get("resolution", ["0", "0"])[0] == resolution:
                    return image.get("href", None)
    return None

# PLAYBACK CHANNEL
def get_channel(url, session, enable_ts=False):

    license_url = "https://vmxdrmfklb1.sfm.t-online.de:8063/"
    li = xbmcgui.ListItem(path=url)        

    device_id = session["deviceId"]

    li.setProperty('inputstream.adaptive.license_key', f"{license_url}|deviceId={device_id}|R" + "{SSM}|")
    li.setProperty('inputstream.adaptive.license_type', "com.widevine.alpha")

    li.setProperty('inputstream', 'inputstream.adaptive')
    li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    li.setProperty("IsPlayable", "true")

    li.setInfo("video", {"title": xbmc.getInfoLabel("ListItem.Label"), "plot": xbmc.getInfoLabel("ListItem.Plot")})
    li.setArt({'thumb': xbmc.getInfoLabel("ListItem.Thumb")})

    xbmc.executebuiltin( "Dialog.Close(busydialognocancel)" )

    xbmcplugin.setResolvedUrl(__addon_handle__, True, li)

    if "_ts_ir" in url:
        url = url.split("|")[1]

    t = xbmc.Player()
    t.play(item=url, listitem=li)
    
    time.sleep(30)

    if t.isPlaying() and not t.isExternalPlayer():
        window_id = xbmcgui.getCurrentWindowId()
        x = Thread(target=refresh_window, args=(datetime.datetime.now().timestamp(), window_id, ))
        x.start()
    
    return

# CREATE CHECKSUM
def checksum(id, session):
    
    # GET PSK
    url = "https://web.magentatv.de/meine-inhalte/cloud-aufnahmen"
    req = requests.get(url, headers=header)
    psk = b64decode(str(req.content).split('"id2":"')[1].split('"')[0]).decode()

    # CREATE KEY
    v = f"{psk}{session['userData']['userID']}{session['userData']['encryptToken']}{session['cnonce']}"
    sha256 = hashlib.sha256()
    sha256.update(v.encode())
    sha256 = sha256.hexdigest()
    key = sha256.upper()

    # CREATE CHECKSUM
    sig = hmac.new(bytes(key, 'latin-1'), msg=bytes(id, 'latin-1'), digestmod=hashlib.sha256).hexdigest()
    
    return sig


#
# TV MENU
#

def tv_browser(url=None):
    
    session = login("ngtvepg")
    enable_e = __addon__.getSetting("e")
    enable_s = __addon__.getSetting("s")

    ch_list = get_channel_list(session, enable_e, enable_s)

    if url is None:
        tv_menu_creator(ch_list, session)
    else:
        get_channel(url, session)

# RETRIEVE THE CHANNEL DICT
def get_channel_list(session, enable_e, enable_s):
    
    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/AllChannel"
    data = '{"channelNamespace":"12","filterlist":[{"key":"IsHide","value":"-1"}],"metaDataVer":"Channel/1.1","properties":[{"include":"/channellist/logicalChannel/contentId,/channellist/logicalChannel/name,/channellist/logicalChannel/chanNo,/channellist/logicalChannel/externalCode,/channellist/logicalChannel/categoryIds,/channellist/logicalChannel/introduce,/channellist/logicalChannel/pictures/picture/href,/channellist/logicalChannel/pictures/picture/imageType,/channellist/logicalChannel/physicalChannels/physicalChannel/mediaId,/channellist/logicalChannel/physicalChannels/physicalChannel/definition,/channellist/logicalChannel/physicalChannels/physicalChannel/externalCode,/channellist/logicalChannel/physicalChannels/physicalChannel/fileFormat","name":"logicalChannel"}],"returnSatChannel":0}'
    epg_cookies = session["cookies"]
    header.update({"X_CSRFToken": session["cookies"]["CSRFSESSION"]})

    req = requests.post(url, data=data, headers=header, cookies=epg_cookies)

    ch_list = {i["contentId"]: {"name": i["name"], "img": i["pictures"][0]["href"], "media": {
        m["mediaId"]: m["externalCode"] for m in i["physicalChannels"]}} for i in req.json()["channellist"]}

    request_string = ""
    for i in ch_list.keys():
        request_string = request_string + '{"channelId":"' + i + '","type":"VIDEO_CHANNEL"},'
    request_string = request_string[:-1]

    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/AllChannelDynamic"
    data = '{"channelIdList":[' + request_string + '],"channelNamespace":"12","filterlist":[{"key":"IsHide","value":"-1"}],"properties":[{"include":"/channelDynamicList/logicalChannelDynamic/contentId,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/mediaId,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/playurl,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/btvBR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/btvCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/cpvrRecBR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/cpvrRecCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/pltvCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/pltvBR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/irCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/irBR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/npvrRecBR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/npvrRecCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/npvrOnlinePlayCR,/channelDynamicList/logicalChannelDynamic/physicalChannels/physicalChannelDynamic/npvrOnlinePlayBR","name":"logicalChannelDynamic"}]}'
    epg_cookies = session["cookies"]
    header.update({"X_CSRFToken": session["cookies"]["CSRFSESSION"]})

    req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
    dynamic_list = req.json()["channelDynamicList"]

    add_url = "https://raw.githubusercontent.com/sunsettrack4/script.service.magentatv/master/channels.json"
    add_req = requests.get(add_url)
    add_dict = add_req.json()

    for entry in dynamic_list:
        ch = ch_list[entry['contentId']]
        for pchannel in entry['physicalChannels']:
            if "playurl" not in pchannel:
                if enable_e == "true":
                    if add_dict["e"].get(pchannel['mediaId']):
                        ch['playurl'] = f"https://svc40.main.sl.t-online.de/LCID3221228{add_dict['e'][pchannel['mediaId']]}.originalserver.prod.sngtv.t-online.de/PLTV/88888888/224/3221228{add_dict['e'][pchannel['mediaId']]}/3221228{add_dict['e'][pchannel['mediaId']]}.mpd"
                if enable_s == "true":
                    if add_dict["s"].get(pchannel['mediaId']):
                        ch['playurl'] = f"https://svc40.main.sl.t-online.de/LCID3221228{add_dict['s'][pchannel['mediaId']]}.originalserver.prod.sngtv.t-online.de/PLTV/88888888/224/3221228{add_dict['s'][pchannel['mediaId']]}/3221228{add_dict['s'][pchannel['mediaId']]}.mpd"
                break
            playurl = pchannel['playurl']
            manifest_name = ch["media"][pchannel['mediaId']]
            if "DASH_OTT-FOUR_K" in manifest_name:
                ch['playurl_4k'] = playurl
                continue
            if "DASH_OTT-HD" in manifest_name:
                ch['playurl'] = playurl
                break
            elif "DASH_OTT-SD" in manifest_name:
                ch['playurl'] = playurl
    
    return ch_list

# CREATE THE CHANNEL LIST
def tv_menu_creator(ch_list, session):
    menu_listing = []
    epg_dict = dict()

    time_start = str(datetime.datetime.now().replace(tzinfo=local_timezone).astimezone(datetime.timezone.utc).strftime("%Y%m%d%H%M%S"))
    time_end = str(((datetime.datetime.now().replace(tzinfo=local_timezone).astimezone(datetime.timezone.utc)) + datetime.timedelta(minutes=1)).strftime("%Y%m%d%H%M%S"))

    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/PlayBillList"
    guide_data = f'{{"type":2,"isFiltrate":0,"orderType":4,"isFillProgram":1,"channelNamespace":"2","offset":0,' \
                     f'"count":-1,"properties":[{{"name":"playbill","include":"subName,id,name,starttime,endtime,' \
                     f'channelid,ratingid,genres,introduce,cast,genres,country,pictures,producedate,' \
                     f'seasonNum,subNum"}}],' \
                     f'"endtime":"{time_end}",' \
                     f'"begintime":"{time_start}"}}'

    req = requests.post(url, data=guide_data, cookies=session["cookies"], headers={"X_CSRFToken": session["cookies"]["CSRFSESSION"]})
    epg = req.json()

    for programme in epg["playbilllist"]:
        if not epg_dict.get(programme["channelid"], False):
            epg_dict[programme["channelid"]] = []
        epg_dict[programme["channelid"]].append(
            {"s": programme["starttime"], 
             "e": programme["endtime"],
             "d": programme.get("introduce", "Keine Sendungsdaten vorhanden"),
             "i": get_image(programme.get("pictures")),
             "t": programme.get("name", "")})

    for channel_id, ch in ch_list.items():
        if ch.get("playurl_4k"):
            li = xbmcgui.ListItem(label=f"{ch['name']} UHD")
            url = build_url({"tv_url": ch["playurl_4k"]})
        if ch.get("playurl"):
            li = xbmcgui.ListItem(label=ch['name'])
            url = build_url({"tv_url": ch["playurl"]})
        if ch.get("playurl") or ch.get("playurl_4k"):
            li.setArt({"thumb": ch["img"]})
            if epg_dict.get(channel_id):
                info = '[B]' + epg_dict[channel_id][0]['t'] + '[/B] (' + datetime.datetime(*(time.strptime(epg_dict[channel_id][0]['s'].split(' UTC')[0], '%Y-%m-%d %H:%M:%S')[0:6])).replace(tzinfo=datetime.timezone.utc).astimezone(local_timezone).strftime('%H:%M') + ' - ' + datetime.datetime(*(time.strptime(epg_dict[channel_id][0]['e'].split(' UTC')[0], '%Y-%m-%d %H:%M:%S')[0:6])).replace(tzinfo=datetime.timezone.utc).astimezone(local_timezone).strftime('%H:%M') + ' Uhr)\n\n' + epg_dict[channel_id][0]['d']
                li.setArt({"thumb": ch["img"], "fanart": epg_dict[channel_id][0]['i'] if epg_dict[channel_id][0]['i'] is not None else ch["img"]})
                li.setInfo("video", {'plot': info})
            menu_listing.append((url, li, False))

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


#
# PVR MENU
#

def pvr_browser(id=None, media=None, pvr_id=None):

    session = login("ngtvepg")

    pvr_list = get_pvr_list(session)

    if id is None or media is None or pvr_id is None:
        pvr_menu_creator(pvr_list)
    else:
        get_pvr(id, media, pvr_id, session)

# RETRIEVE THE PVR LIST
def get_pvr_list(session):

    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/QueryPVR"
    data = '{"count":-1,"DTQueryType":0,"expandSubTask":2,"isFilter":0,"offset":0,"orderType":1,"type":0}'
    epg_cookies = session["cookies"]
    header.update({"X_CSRFToken": session["cookies"]["CSRFSESSION"]})

    req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
    return req.json()["pvrlist"]

# CREATE THE PVR MENU
def pvr_menu_creator(pvr_list):
    menu_listing = []

    def append_item(i):
        li = xbmcgui.ListItem(label=f'{datetime.datetime(*(time.strptime(i["beginTime"], "%Y%m%d%H%M%S")[0:6])).replace(tzinfo=datetime.timezone.utc).astimezone(local_timezone).strftime("%d.%m.%Y %H:%M")} | {i["channelName"]} | {i["pvrName"]}')
        li.setArt({"thumb": i["channelPictures"][0]["href"], "fanart": get_image(i.get("pictures"))})
        info = "[B]" + i["subName"] + "[/B]\n\n" if i.get("subName") else ""
        li.setInfo("video", {'plot': info + i.get("introduce", "Keine Sendungsinformationen verfügbar")})
        url = build_url({"id": i["channelId"], "media": i["mediaId"], "pvr": i["pvrId"]})
        menu_listing.append((url, li, False))

    for i in pvr_list:
        if i.get("pvrList"):
            for a in i["pvrList"]:
                append_item(a)
        elif i.get("seriesType"):
            continue
        else:
            append_item(i)

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)

# PLAYBACK PVR
def get_pvr(id, media, pvr_id, session):
    
    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/AuthorizeAndPlay"
    data = f'{{"checksum":"{checksum(id, session)}","contentId":"{id}","mediaId":"{media}","pvrId":"{pvr_id}","businessType":8,"contentType":"CHANNEL"}}'
    epg_cookies = session["cookies"]
    header.update({"X_CSRFToken": session["cookies"]["CSRFSESSION"]})

    req = requests.post(url, headers=header, data=data, cookies=epg_cookies)
    playback_url = req.json()["playUrl"]
    
    get_channel(playback_url, session)


#
# VOD MENU
#

# Main Menu
main_query = "whiteLabelId=webClient&$deviceModel=WEB-MTV&$partnerMap=entertaintvOTT_WEB&$profile=stageExt&$subscriberType=OTT_NONDTISP_DT"

main_url = f"https://tvhubs.t-online.de/v2/iptv2015acc/DocumentGroupRedirect/TVHS_DG_MainMenu?{main_query}"
my_url = f"https://tvhubs.t-online.de/v2/iptv2015acc/DocumentGroupRedirect/TVHS_DG_Einstieg_Meine-Inhalte_MTV?{main_query}"
wl_url = f"https://tvhubs.t-online.de/v2/iptv2015acc/DocumentGroupRedirect/TVHS_DG_Einstieg_Merkliste_MTV?{main_query}"

# Get the addon url based on Kodi request
def build_url(query):
    return f"{base_url}?{urllib.parse.urlencode(query)}"

# Load menu item(s)
def menu_loader(item, auth):
    if "http" not in item:
        return
    if auth is True:
        session = login("ngtvvod")
        auth_header = {"authorization": f'TAuth realm="ngtvvod",tauth_token="{session["access_token"]}"'}
    else:
        session = None
        auth_header = header
    item = f'{item.split("&")[0]}&info:bandwidth=20000&info:hdcpVersion=2.2&info:modelId=MR401&info:hdrVersion=HDR10;HLG;Dolby+Vision&$size=1000000000&$offset=0&$profile=stageExt&$deviceModel=WEB-MTV' if not "MainMenu" in item else item
    page = requests.get(item, headers=auth_header)
    return page.json(), session

# Create Kodi menu based on json response
def menu_creator(item, session):
    menu_listing = []

    if not item.get("$type"):
        return

    # Main Menu
    if item["$type"] == "menu":
        for i in item["menuItems"]:
            if "https" in i["screen"]["href"]:
                li = xbmcgui.ListItem(label=i['title'])
                url = build_url({"url": i["screen"]["href"]})
                menu_listing.append((url, li, True))

    # Tag
    if item["$type"] == "tag":
        for b in item["content"]["items"]:
            if b.get("assetDetails"):
                if b["assetDetails"]["type"] in ("Movie", "Series", "Season", "Episode"):
                    li = xbmcgui.ListItem(label=f'{b["assetDetails"]["multiAssetInformation"]["seriesTitle"] + " - " if b["assetDetails"]["type"] in ("Episode", "Season") else ""}{b["assetDetails"]["multiAssetInformation"]["seasonTitle"] + " - " if b["assetDetails"]["type"] == "Episode" else ""}{b["assetDetails"]["contentInformation"]["title"]}')
                    li.setInfo("video", {'plot': b["assetDetails"]["contentInformation"].get("longDescription", b["assetDetails"]["contentInformation"].get("description"))})
                    if len(b["assetDetails"]["contentInformation"]["images"]) > 1:
                        li.setArt({"thumb": b["assetDetails"]["contentInformation"]["images"][0]["href"], "fanart": b["assetDetails"]["contentInformation"]["images"][-1]["href"]})
                    else:
                        li.setArt({"thumb": b["assetDetails"]["contentInformation"]["images"][0]["href"], "fanart": b["assetDetails"]["contentInformation"]["images"][0]["href"]})
                    url = build_url({"url": b["assetDetails"]["contentInformation"]["detailPage"]["href"]})
                    menu_listing.append((url, li, True))

    # MyMovies
    if item["$type"] == "mymovies":
        for i in item["content"]["items"]:
            li = xbmcgui.ListItem(label=i["contentInformation"]['title'])
            li.setInfo("video", {'plot': i["contentInformation"].get("longDescription", i["contentInformation"].get("description"))})
            if len(i["contentInformation"]["images"]) > 1:
                li.setArt({"thumb": i["contentInformation"]["images"][0]["href"], "fanart": i["contentInformation"]["images"][-1]["href"]})
            else:
                li.setArt({"thumb": i["contentInformation"]["images"][0]["href"], "fanart": i["contentInformation"]["images"][0]["href"]})
            url = build_url({"url": i["contentInformation"]["detailPage"]["href"], "auth": True})
            menu_listing.append((url, li, True))
    
    # Structured Grid
    if item["$type"] == "structuredgrid":
        for i in item["content"]["lanes"]:
            if i["type"] in ("UnstructuredGrid", "MyMovies", "Watchlist"):
                li = xbmcgui.ListItem(label=i['title'])
                if len(i.get("technicalTiles", [])) > 0 and not i["type"] in ("MyMovies", "Watchlist"):
                    if i["technicalTiles"][0]["teaser"]["title"] == "Alle anzeigen" and i["title"] != "MEGATHEK: GENRES":
                        li.setInfo("video", {'plot': i["technicalTiles"][0]["teaser"].get("description")})
                        url = build_url({"url": i["technicalTiles"][0]["teaser"]["details"]["href"]})
                    else:
                        url = build_url({"url": i["laneContentLink"]["href"]})
                else:
                    url = build_url({"url": i["laneContentLink"]["href"], "auth": True if session is not None else False})
                menu_listing.append((url, li, True))

    # Unstructured Grid
    if item["$type"] in ("unstructuredgrid", "unstructuredgridlane"):
        for i in item["content"]["items"]:
            url = None
            if i["type"] in ("Asset", "Teaser"):
                if i.get("details"):
                    url = build_url({"url": i["details"]["href"]})
                elif i.get("buttons"):
                    if i["buttons"][0].get("details"):
                        url = build_url({"url": i["buttons"][0]["details"]["href"]})
                if i["type"] == "Teaser":
                    if i.get("stageTitle"):
                        li = xbmcgui.ListItem(label=i['stageTitle'])
                    else:
                        li = xbmcgui.ListItem(label=i['title'])
                else:
                    if i.get("seriesTitle") and i["vodType"] == "Season":
                        li = xbmcgui.ListItem(label=f"{i['seriesTitle']} - {i['title']}")    
                    else:
                        li = xbmcgui.ListItem(label=i['title'])
                if i["type"] in ("Asset", "Teaser"):
                    li.setInfo("video", {'plot': i.get("longDescription", i.get("description"))})
                    li.setArt({"thumb": i.get("image", i.get("stageImage", {"href": ""}))["href"], "fanart": i.get("image", i.get("stageImage", {"href": ""}))["href"]})
                if url:
                    menu_listing.append((url, li, True))

    # Asset Details
    if item["$type"] == "assetdetails":

        # SEASON
        if item["content"]["type"] in ("Season", "Series"):
            for a in item["content"]["multiAssetInformation"]["subAssetDetails"]:
                info = a["contentInformation"].get("description")
                if len(a["contentInformation"]["images"]) > 1:
                    pics = [a["contentInformation"]["images"][0]["href"], a["contentInformation"]["images"][-1]["href"]]
                else:
                    pics = [a["contentInformation"]["images"][0]["href"], a["contentInformation"]["images"][0]["href"]]
                if item["content"]["type"] == "Series":
                    li = xbmcgui.ListItem(label=f'{item["content"]["contentInformation"]["title"]} - {a["contentInformation"]["title"]}')
                    li.setInfo("video", {'plot': info})
                    li.setArt({"thumb": pics[0], "fanart": pics[1]})
                    url = build_url({"url": a["contentInformation"]["detailPage"]["href"]})
                    menu_listing.append((url, li, True))
                if item["content"]["type"] == "Season":
                    for i in a["partnerInformation"]:
                        if i.get("features", False) and len(i["features"]) > 0:
                            li = xbmcgui.ListItem(label=f'{item["content"]["multiAssetInformation"]["seriesTitle"]} - {a["contentInformation"]["title"]} ({i["partnerId"].upper()})')
                            li.setInfo("video", {'plot': info})
                            li.setArt({"thumb": pics[0], "fanart": pics[1]})
                            url = build_url({"url": i["features"][0]["player"]["href"], "auth": True})
                            menu_listing.append((url, li, False))

        # MOVIE / EPISODE
        if item["content"]["type"] in ("Movie", "Episode"):

            # MAIN
            for i in item["content"]["partnerInformation"]:
                for a in i["features"]:
                    li = xbmcgui.ListItem(label=f'{a["featureType"]} ({i["name"]})')
                    li.setInfo("video", {'plot': item["content"]["contentInformation"].get("longDescription", item["content"]["contentInformation"].get("description"))})
                    if len(item["content"]["contentInformation"]["images"]) > 1:
                        li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][-1]["href"]})
                    else:
                        li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][0]["href"]})
                    url = build_url({"url": a["player"]["href"], "auth": True})
                    menu_listing.append((url, li, False))

            # TRAILER
            for i in item["content"]["contentInformation"]["trailers"]:
                li = xbmcgui.ListItem(label="Trailer")
                li.setInfo("video", {'plot': item["content"]["contentInformation"].get("longDescription", item["content"]["contentInformation"].get("description"))})
                if len(item["content"]["contentInformation"]["images"]) > 1:
                    li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][1]["href"]})
                else:
                    li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][0]["href"]})
                url = build_url({"url": i["href"]})
                menu_listing.append((url, li, False))

    # Player
    if item["$type"] == "player":
        q = dict()
        pid = item["content"]["feature"]["metadata"].get("cmlsId", "")
        stream_id = item["content"]["feature"]["metadata"].get("id", "")
        for i in item["content"]["feature"]["representations"]:
            if i["type"] in ("MpegDash", "MpegDashTranscoded") and len(i["contentPackages"]) > 0:
                q[i["quality"]] = {"url": i["contentPackages"][0]["media"]["href"], "c_no": i["contentPackages"][0]["contentNumber"]}
        if hasattr(sys, "getandroidapilevel") or platform.system() == "Windows":
            if q.get("UHD"):
                url = q["UHD"]["url"]
                c_no = q["UHD"]["c_no"]
            elif q.get("HD"):
                url = q["HD"]["url"]
                c_no = q["HD"]["c_no"]
            elif q.get("SD"):
                url = q["SD"]["url"]
                c_no = q["SD"]["c_no"]
            else:
                xbmcgui.Dialog().notification(__addonname__, "Der Inhalt kann nicht wiedergegeben werden. [0]", xbmcgui.NOTIFICATION_INFO)
                return
        else:
            if not q.get("SD", False):
                xbmcgui.Dialog().notification(__addonname__, "Der Inhalt kann nicht wiedergegeben werden. [1]", xbmcgui.NOTIFICATION_INFO)
                return
            url = q["SD"]["url"]
            c_no = q["SD"]["c_no"]
        
        if session is not None:
            auth_header = {"authorization": f'TAuth realm="ngtvvod",tauth_token="{session["access_token"]}"', "x-device-authorization": f'TAuth realm="device",device_token="{session["deviceToken"]}"'}
            try:
                position = requests.get("https://wcps.t-online.de/vphs/v1/default/PlaybackHistory/ids", headers=auth_header)
                position = [i["position"] for i in position.json()["items"] if i["assetId"] == pid][0]
            except:
                position = 0
        else:
            auth_header = header
            position = 0
        
        media = requests.get(url, headers=auth_header)
        stream_url = xmltodict.parse(media.content)["smil"]["body"]["seq"]["media"]["@src"]

        details = item["content"]["feature"]["metadata"]
        
        li = xbmcgui.ListItem(path=stream_url)

        if session is not None:
            license_url = "https://licf-iptv.dmm.t-online.de/v1.0/WidevineLicenseAcquisition.ashx"
            
            lapb = '<lapb version="2"><contentNo>' + c_no + '</contentNo><profile>sl-windows</profile><auth type="sts">' + session["access_token"] + '</auth><agent>WEB-MTV</agent><recovery allow="false"/><requestId>' + str(uuid4()) + '</requestId><serviceId>MAGENTATVAPP</serviceId></lapb>'            
            lapb_encoded = urllib.parse.quote(b64encode(lapb.encode()).decode())

            device_id = session["deviceId"]
            device_id_encoded = b64encode(device_id.encode()).decode()

            li.setProperty('inputstream.adaptive.license_key', license_url + "|" + f'CustomDeviceId={device_id_encoded}&LAPB={lapb_encoded}' + "|R{SSM}|")
            li.setProperty('inputstream.adaptive.license_type', "com.widevine.alpha")

        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'mpd')
        li.setProperty("IsPlayable", "true")

        title = details["title"] + " (Trailer)" if not session else f'{details["seriesTitle"]} - {details["title"]}' if details.get("seriesTitle", False) else details["title"]
        li.setInfo("video", {"title": title, 'plot': xbmc.getInfoLabel("ListItem.Plot"), 'genre': details.get("mainGenre"), 'year': details.get("yearOfProduction"), 'duration': details["runtimeInSeconds"]})
        li.setArt({'thumb': xbmc.getInfoLabel("ListItem.Thumb")})

        xbmcplugin.setResolvedUrl(__addon_handle__, True, li)

        t = xbmc.Player()
        t.play(item=stream_url, listitem=li)
        
        if position > 0:
            pos = xbmcgui.Dialog().yesno("Weiterschauen", "Möchten Sie die Wiedergabe an der zuletzt gespeicherten Position fortsetzen?")
            if pos:
                if position > t.getTime():
                    t.seekTime(position - int(t.getTime()))
                else:
                    t.seekTime(int(t.getTime()) - position)
        
        x = Thread(target=watch, args=(t, auth_header, stream_id))
        x.start()
        
        return

    if len(menu_listing) == 0:
        xbmcgui.Dialog().notification(__addonname__, "Keine Inhalte gefunden", xbmcgui.NOTIFICATION_INFO)
        return

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)


#
# REFRESH THREAD
#

def refresh_window(init_time, window_id):
    while True:
        if xbmcgui.getCurrentWindowId() != window_id and init_time + 30 < datetime.datetime.now().timestamp():
            xbmc.executebuiltin("Container.Refresh")
            break
        time.sleep(1)


#
# VIDEO PLAYER THREAD
#

def watch(t, auth, stream_id):
    id_time = 0
    
    while not t.isPlaying():  # not started yet
        time.sleep(1)
    while t.isPlaying():  # track progress
        try:
            if t.getTime() > 0:
                id_time = int(t.getTime())
        except:
            pass
    
    data = {"audioLanguage": "de", "position": id_time, "subtitleLanguage": "off"}
    auth.update({'Content-Type': 'application/x-www-form-urlencoded'})
    
    requests.post(f"https://wcps.t-online.de/vphs/v1/default/PlaybackHistory/{stream_id}/Main%20Movie", headers=auth, data=data)
        

#
# ROUTER
#

# Router function calling other functions of this script
def router(item):

    def vod_browser():
        m = menu_loader(url, auth)
        menu_creator(m[0], m[1]) if m is not None else []

    params = dict(urllib.parse.parse_qsl(item[1:]))
    menu_listing = []

    if params:
        # VOD BROWSER - MAIN MENU
        if params.get("feature", "") == "VOD":
            url = main_url
            auth = False
            vod_browser()

        # LIVE TV
        elif params.get("feature", "") == "TV":
            tv_browser()

        # PVR
        elif params.get("feature", "") == "PVR":
            pvr_browser()

        # MY CONTENTS
        elif params.get("feature", "") == "ML":
            url = my_url
            auth = True
            vod_browser()

        # MY WATCHLIST
        elif params.get("feature", "") == "WL":
            url = wl_url
            auth = True
            vod_browser()

        # VOD BROWSER - SUBMENU
        elif params.get("url"):
            url = params["url"]
            if params.get("auth"):
                auth = True if params["auth"] == "True" else False
            else:
                auth = False
            if auth:
                xbmc.executebuiltin( "ActivateWindow(busydialognocancel)" )
                try:
                    vod_browser()
                except:
                    pass
                xbmc.executebuiltin( "Dialog.Close(busydialognocancel)" )
            else:
                vod_browser()

        # LIVE TV STREAM
        elif params.get("tv_url"):
            xbmc.executebuiltin( "ActivateWindow(busydialognocancel)" )
            try:
                tv_browser(params["tv_url"])
            except:
                xbmc.executebuiltin( "Dialog.Close(busydialognocancel)" )

        # PVR STREAM
        elif params.get("id") and params.get("media") and params.get("pvr"):
            xbmc.executebuiltin( "ActivateWindow(busydialognocancel)" )
            try:
                pvr_browser(params["id"], params["media"], params["pvr"])
            except:
                xbmc.executebuiltin( "Dialog.Close(busydialognocancel)" )

    else:
        # MAIN MENU
        for i in [("Video on Demand", "VOD"), ("Live TV", "TV"), ("Meine Aufnahmen", "PVR"), ("Meine Inhalte", "ML"), ("Meine Merkliste", "WL")]:
            li = xbmcgui.ListItem(label=i[0])
            url = build_url({"feature": i[1]})
            menu_listing.append((url, li, True))

        xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
        xbmcplugin.endOfDirectory(__addon_handle__)
    

#
# AUTHENTICATION
#

# LOGIN TO WEBSERVICE, SAVE TOKENS AND DEVICE ID
def login(scope):
    __login = __addon__.getSetting("username")
    __password = __addon__.getSetting("password")
    return refresh_process(login_process(__login, __password), scope)

# RETRIEVE HIDDEN XSRF + TID VALUES TO BE TRANSMITTED TO ACCOUNTS PAGE
def parse_input_values(content):
    f = dict()

    parser = BeautifulSoup(content, 'html.parser')
    ref = parser.findAll('input')

    for i in ref:
        if "xsrf" in i.get("name", "") or i.get("name", "") == "tid":
            f.update({i["name"]: i["value"]})
    
    return f

# INITIAL LOGIN
def login_process(__username, __password):
    """Login to Magenta TV via webpage using the email address as username"""

    session = dict()
    uu_id = str(uuid4())
    cnonce = hashlib.md5()
    cnonce.update(f'{str(datetime.datetime.now().timestamp()).replace(".", "")[0:-3]}:00'.encode())
    cnonce = cnonce.hexdigest()
    

    #
    # RETRIEVE SESSION DATA
    #

    # STEP 1: GET COOKIE TOKEN (GET REQUEST)
    url = "https://accounts.login.idm.telekom.com/oauth2/auth?client_id=10LIVESAM30000004901NGTVMAGENTA000000000&redirect_uri=https%3A%2F%2Fweb.magentatv.de%2Fauthn%2Fidm&response_type=code&scope=openid+offline_access"
    req = requests.get(url, headers=header)
    cookies = req.cookies.get_dict()

    # STEP 2: SEND USERNAME/MAIL 
    data = {"x-show-cancel": "false", "bdata": "", "pw_usr": __username, "pw_submit": "", "hidden_pwd": ""}
    data.update(parse_input_values(req.content))

    url_post = "https://accounts.login.idm.telekom.com/factorx"
    req = requests.post(url_post, cookies=cookies, data=data, headers=header)
    cookies = req.cookies.get_dict()

    # STEP 3: SEND PASSWORD
    data = {"hidden_usr": __username, "bdata": "", "pw_pwd": __password, "pw_submit": ""}
    data.update(parse_input_values(req.content))

    req = requests.post(url_post, cookies=cookies, data=data, headers=header)
    code = req.url.split("=")[1]

    # STEP 4: RETRIEVE ACCESS TOKEN FOR USER
    url = "https://accounts.login.idm.telekom.com/oauth2/tokens"
    data = {"scope": "openid", "code": code, "grant_type": "authorization_code", "redirect_uri": "https://web.magentatv.de/authn/idm", "client_id": "10LIVESAM30000004901NGTVMAGENTA000000000", "claims": '{"id_token":{"urn:telekom.com:all":{"essential":false}}}'}

    req = requests.post(url, cookies=cookies, data=data, headers=header)
    bearer = req.json()
    
    # STEP 5: UPDATE ACCESS TOKEN FOR TV/EPG
    data = {"scope": "ngtvepg", "grant_type": "refresh_token", "refresh_token": bearer["refresh_token"], "client_id": "10LIVESAM30000004901NGTVMAGENTA000000000"}

    req = requests.post(url, cookies=cookies, data=data, headers=header)
    bearer = req.json()
    
    # STEP 6: EPG GUEST AUTH - JSESSION
    url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/Login?&T=Windows_chrome_86"
    data = {"userId": "Guest", "mac": "00:00:00:00:00:00"}

    req = requests.post(url, data=data, headers=header)
    j_session = req.cookies.get_dict()["JSESSIONID"]

    # STEP 7: EPG USER AUTH - ALL SESSIONS
    url = 'https://api.prod.sngtv.magentatv.de/EPG/JSON/Authenticate?SID=firstup&T=Windows_chrome_86'
    data = '{"terminalid":"' + uu_id + '","mac":"' + uu_id + '","terminaltype":"WEBTV","utcEnable":1,"timezone":"UTC","userType":3,"terminalvendor":"Unknown","preSharedKeyID":"PC01P00002","cnonce":"' + cnonce + '"}'
    epg_cookies = {"JSESSIONID": j_session}

    req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
    epg_cookies = req.cookies.get_dict()

    # STEP 8: GET DEVICE ID TO ACCESS WIDEVINE DRM STREAMS
    x = 0
    while True:
        # 8.1: AUTHENTICATE
        url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/DTAuthenticate"
        data = '{"areaid":"1","cnonce":"' + cnonce + '","mac":"' + uu_id + '","preSharedKeyID":"NGTV000001","subnetId":"4901","templatename":"NGTV","terminalid":"' + uu_id + '","terminaltype":"WEB-MTV","terminalvendor":"WebTV","timezone":"UTC","usergroup":"OTT_NONDTISP_DT","userType":"1","utcEnable":1,"accessToken":"' + f'{bearer["access_token"]}' + '","caDeviceInfo":[{"caDeviceId":"' + uu_id + '","caDeviceType":8}],"connectType":1,"osversion":"Windows 10","softwareVersion":"1.63.2","terminalDetail":[{"key":"GUID","value":"' + uu_id + '"},{"key":"HardwareSupplier","value":"WEB-MTV"},{"key":"DeviceClass","value":"TV"},{"key":"DeviceStorage","value":0},{"key":"DeviceStorageSize","value":0}]}'

        req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
        user_data = req.json()
        
        if "success" in user_data["retmsg"]:
            break
        
        # 8.2: RETRIEVE AVAILABLE WEBTV DEVICE
        url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/GetDeviceList"
        data = '{"deviceType":"2;0;5;17","userid":"' + user_data["userID"] + '"}'

        req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
        device_data = req.json()

        for i in device_data["deviceList"]:
            if i.get("deviceName", "") == "WebTV":
                uu_id = i["physicalDeviceId"]
                break
        
        x = x + 1
        if x > 8:
            raise Exception("Error: Authentication failure")
             
    
    # SETUP SESSION
    session.update({"deviceId": req.json()["caDeviceInfo"][0]["VUID"]})  # DEVICE/TERMINAL ID
    session.update(bearer)  # TOKENS (SCOPE: NGTVEPG)
    session.update({"cookies": req.cookies.get_dict()})  # EPG COOKIES
    session.update({"userData": user_data})  # AUTH DATA
    session.update({"cnonce": cnonce})  # CNONCE
    
    # RETURN USER-SPECIFIC COOKIE VALUES
    return session

# REFRESH SESSION FOR VOD
def refresh_process(session, scope):
    if scope == "ngtvepg":
        return session

    url = "https://accounts.login.idm.telekom.com/oauth2/tokens"
    data = {"scope": scope, "grant_type": "refresh_token", "refresh_token": session['refresh_token'], "client_id": "10LIVESAM30000004901NGTVMAGENTA000000000"}

    req = requests.post(url, data=data, headers=header)

    # RETURN UPDATED AUTH_TOKEN
    session.update(req.json())  # TOKENS (SCOPE: NGTVVOD)

    url = f"https://wcps.t-online.de/bootstrap/iptv2015/v1/manifest?model=WEB-MTV&deviceId={session['deviceId']}&appname=vod&appVersion=1632&firmware=Windows+10&runtimeVersion=Mozilla%2F5.0+%28Windows+NT+10.0%3B+Win64%3B+x64%29+AppleWebKit%2F537.36+%28KHTML%2C+like+Gecko%29+Chrome%2F108.0.0.0+Safari%2F537.36&duid={session['deviceId']}%7Cresolution%3Dhdr&$redirect=false"
    req = requests.get(url, headers=header)

    # GET DEVICE TOKEN
    session.update({"deviceToken": req.json()["sts"]["deviceToken"]})  # DEVICE TOKEN

    return session


if __name__ == "__main__":
    router(sys.argv[2])