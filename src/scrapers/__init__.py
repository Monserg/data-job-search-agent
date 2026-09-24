from . import (
    djinni,
    dou,
    remoteok,
    weworkremotely,
    robota_ua,
    work_ua_email,
    nofluffjobs,
    justremote,
    indeed,
    linkedin_alerts,
    remotive,
    himalayas,
)

# Ім'я в config.yaml -> модуль зі search()
REGISTRY = {
    "djinni": djinni,
    "dou": dou,
    "remoteok": remoteok,
    "weworkremotely": weworkremotely,
    "robota_ua": robota_ua,
    "work_ua_email": work_ua_email,
    "nofluffjobs": nofluffjobs,
    "justremote": justremote,
    "indeed": indeed,
    "linkedin_alerts": linkedin_alerts,
    "remotive": remotive,
    "himalayas": himalayas,
}
