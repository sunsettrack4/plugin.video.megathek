import json, sys
import xbmc

video_id = sys.argv[1]
data_dir = sys.argv[2]

if video_id is None or video_id in ("", "_TRAILER"):
    pass
else:
    video_id = str(video_id)
    try:
        with open(f"{data_dir}/watched_list.json", "r", encoding="UTF-8") as file:
            f = json.loads(file.read())
    except:
        f = []

    if video_id in f:
        f.remove(video_id)
    else:
        f.append(video_id)

    try:
        with open(f"{data_dir}/watched_list.json", "w", encoding="UTF-8") as file:
            file.write(json.dumps(f))
    except:
        pass

    xbmc.executebuiltin("Container.Refresh")