from base64 import b64encode
from bs4 import BeautifulSoup
from uuid import uuid4
import requests, sys, urllib, xmltodict
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs


__addon__ = xbmcaddon.Addon()
__addonname__ = __addon__.getAddonInfo('name')
data_dir = xbmcvfs.translatePath(__addon__.getAddonInfo('profile'))

base_url = sys.argv[0]
__addon_handle__ = int(sys.argv[1])
args = urllib.parse.parse_qs(sys.argv[2][1:])
lang = "de" if xbmc.getLanguage(xbmc.ISO_639_1) == "de" else "en"

xbmcplugin.setContent(__addon_handle__, 'videos')

# DEFAULT HEADER
header = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded"}

#
# MENU
#

# Main Menu
main_query = "whiteLabelId=webClient&$deviceModel=WEB-MTV&$partnerMap=entertaintvOTT_WEB&$profile=stageExt&$subscriberType=OTT_NONDTISP_DT"
main_url = f"https://tvhubs.t-online.de/v2/iptv2015acc/DocumentGroupRedirect/TVHS_DG_MainMenu?{main_query}"

# Get the addon url based on Kodi request
def build_url(query):
    return f"{base_url}?{urllib.parse.urlencode(query)}"

# Load menu item(s)
def menu_loader(item, auth=False):
    if auth:
        session = login()
        auth_header = {"authorization": f'TAuth realm="ngtvvod",tauth_token="{session["access_token"]}"'}
    else:
        session = None
        auth_header = header
    item = f'{item.split("&")[0]}&$size=1000000000&$offset=0&$profile=stageExt&$deviceModel=WEB-MTV' if not "MainMenu" in item else item
    page = requests.get(item, headers=auth_header)
    return page.json(), session

# Create Kodi menu based on json response
def menu_creator(item, session):
    menu_listing = []

    if not item.get("$type"):
        return

    # (Main) Menu
    if item["$type"] == "menu":
        for i in item["menuItems"]:
            if "https" in i["screen"]["href"]:
                li = xbmcgui.ListItem(label=i['title'])
                url = build_url({"url": i["screen"]["href"]})
                menu_listing.append((url, li, True))
    
    # Structured Grid
    if item["$type"] == "structuredgrid":
        for i in item["content"]["lanes"]:
            if i["type"] == "UnstructuredGrid":
                li = xbmcgui.ListItem(label=i['title'])
                if len(i.get("technicalTiles", [])) > 0:
                    if i["technicalTiles"][0]["teaser"]["title"] == "Alle anzeigen" and i["title"] != "MEGATHEK: GENRES":
                        li.setInfo("video", {'plot': i["technicalTiles"][0]["teaser"].get("description")})
                        url = build_url({"url": i["technicalTiles"][0]["teaser"]["details"]["href"]})
                    else:
                        url = build_url({"url": i["laneContentLink"]["href"]})
                else:
                    url = build_url({"url": i["laneContentLink"]["href"]})
                menu_listing.append((url, li, True))

    # Unstructured Grid
    if item["$type"] in ("unstructuredgrid", "unstructuredgridlane"):
        for i in item["content"]["items"]:
            if i["type"] in ("Asset", "Teaser"):
                if i.get("details"):
                    url = build_url({"url": i["details"]["href"]})
                elif i.get("buttons"):
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
                menu_listing.append((url, li, True))

    # Asset Details
    if item["$type"] == "assetdetails":

        # SEASON
        if item["content"]["type"] in ("Season", "Series"):
            for i in item["content"]["partnerInformation"]:
                # if i["name"] == "MEGATHEK":
                    for a in item["content"]["multiAssetInformation"]["subAssetDetails"]:
                        if item["content"]["type"] == "Series":
                            li = xbmcgui.ListItem(label=f'{item["content"]["contentInformation"]["title"]} - {a["contentInformation"]["title"]} ({i["name"]})')
                        if item["content"]["type"] == "Season":
                            li = xbmcgui.ListItem(label=f'{item["content"]["multiAssetInformation"]["seriesTitle"]} - {a["contentInformation"]["title"]} ({i["name"]})')
                        li.setInfo("video", {'plot': a["contentInformation"].get("description")})
                        if len(a["contentInformation"]["images"]) > 1:
                            li.setArt({"thumb": a["contentInformation"]["images"][0]["href"], "fanart": a["contentInformation"]["images"][-1]["href"]})
                        else:
                            li.setArt({"thumb": a["contentInformation"]["images"][0]["href"], "fanart": a["contentInformation"]["images"][0]["href"]})
                        if item["content"]["type"] == "Series":
                            url = build_url({"url": a["contentInformation"]["detailPage"]["href"]})
                            menu_listing.append((url, li, True))
                        if len(a["partnerInformation"]) > 0 and a["partnerInformation"][0].get("features", False) and len(a["partnerInformation"][0]["features"]) > 0 and item["content"]["type"] == "Season":
                            url = build_url({"url": a["partnerInformation"][0]["features"][0]["player"]["href"], "auth": True})
                            menu_listing.append((url, li, False))

        # MOVIE / EPISODE
        if item["content"]["type"] in ("Movie", "Episode"):
            # MAIN
            for i in item["content"]["partnerInformation"]:
                # if i["name"] == "MEGATHEK":
                    for a in i["features"]:
                        li = xbmcgui.ListItem(label=f'{a["featureType"]} ({i["name"]})')
                        li.setInfo("video", {'plot': item["content"]["contentInformation"].get("longDescription", item["content"]["contentInformation"].get("description"))})
                        if len(item["content"]["contentInformation"]["images"]) > 1:
                            li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][-1]["href"]})
                        else:
                            li.setArt({"thumb": item["content"]["contentInformation"]["images"][0]["href"], "fanart": item["content"]["contentInformation"]["images"][0]["href"]})
                        url = build_url({"url": a["player"]["href"], "auth": True})
                        if i["buyPrice"] == 0:
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
        for i in item["content"]["feature"]["representations"]:
            if i["type"] in ("MpegDash", "MpegDashTranscoded") and len(i["contentPackages"]) > 0:
                url = i["contentPackages"][0]["media"]["href"]
                c_no = i["contentPackages"][0]["contentNumber"]
                if i["quality"] == "HD":
                    break
        
        if session is not None:
            auth_header = {"authorization": f'TAuth realm="ngtvvod",tauth_token="{session["access_token"]}"', "x-device-authorization": f'TAuth realm="device",device_token="{session["deviceToken"]}"'}
        else:
            auth_header = header
        
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

        xbmc.Player().play(item=stream_url, listitem=li)
        return

    xbmcplugin.addDirectoryItems(__addon_handle__, menu_listing, len(menu_listing))
    xbmcplugin.endOfDirectory(__addon_handle__)

# Router function calling other functions of this script
def router(item):
    params = dict(urllib.parse.parse_qsl(item[1:]))

    if params:
        url = params.get("url", main_url)
        auth = params.get("auth", False)
    else:
        url = main_url
        auth = False

    m = menu_loader(url, auth)
    menu_creator(m[0], m[1])
    

#
# AUTHENTICATION
#

# LOGIN TO WEBSERVICE, SAVE TOKENS AND DEVICE ID
def login():
    __login = __addon__.getSetting("username")
    __password = __addon__.getSetting("password")
    return refresh_process(login_process(__login, __password))

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
    data = '{"terminalid":"' + uu_id + '","mac":"' + uu_id + '","terminaltype":"WEBTV","utcEnable":1,"timezone":"UTC","userType":3,"terminalvendor":"Unknown","preSharedKeyID":"PC01P00002","cnonce":"aa29eb89d78894464ab9ad3e4797eff6"}'
    epg_cookies = {"JSESSIONID": j_session}

    req = requests.post(url, data=data, headers=header, cookies=epg_cookies)
    epg_cookies = req.cookies.get_dict()

    # STEP 8: GET DEVICE ID TO ACCESS WIDEVINE DRM STREAMS
    x = 0
    while True:
        # 8.1: AUTHENTICATE
        url = "https://api.prod.sngtv.magentatv.de/EPG/JSON/DTAuthenticate"
        data = '{"areaid":"1","cnonce":"aa29eb89d78894464ab9ad3e4797eff6","mac":"' + uu_id + '","preSharedKeyID":"NGTV000001","subnetId":"4901","templatename":"NGTV","terminalid":"' + uu_id + '","terminaltype":"WEB-MTV","terminalvendor":"WebTV","timezone":"Europe/Berlin","usergroup":"OTT_NONDTISP_DT","userType":"1","utcEnable":1,"accessToken":"' + f'{bearer["access_token"]}' + '","caDeviceInfo":[{"caDeviceId":"' + uu_id + '","caDeviceType":8}],"connectType":1,"osversion":"Windows 10","softwareVersion":"1.63.2","terminalDetail":[{"key":"GUID","value":"' + uu_id + '"},{"key":"HardwareSupplier","value":"WEB-MTV"},{"key":"DeviceClass","value":"TV"},{"key":"DeviceStorage","value":0},{"key":"DeviceStorageSize","value":0}]}'

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
            for d in ["MagentaTV Stick", "MagentaTV One", "MagentaTV Box", "MagentaTV Box Play", "WebTV"]:
                if i.get("deviceName", "") == d:
                    uu_id = i["physicalDeviceId"]
                    break
        
        x = x + 1
        if x > 8:
            raise Exception("Error: Authentication failure")
             
    
    # SETUP SESSION
    session.update({"deviceId": req.json()["caDeviceInfo"][0]["VUID"]})  # DEVICE/TERMINAL ID
    session.update(bearer)  # TOKENS (SCOPE: NGTVEPG)
    
    # RETURN USER-SPECIFIC COOKIE VALUES
    return session

# REFRESH SESSION FOR VOD
def refresh_process(session):
    url = "https://accounts.login.idm.telekom.com/oauth2/tokens"
    data = {"scope": "ngtvvod", "grant_type": "refresh_token", "refresh_token": session['refresh_token'], "client_id": "10LIVESAM30000004901NGTVMAGENTA000000000"}

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