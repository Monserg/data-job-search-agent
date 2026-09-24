from . import (
    djinni,
    dou,
    remoteok,
    weworkremotely,
    robota_ua_email,
    work_ua_email,
    nofluffjobs,
    justremote,
    indeed,
    linkedin_email,
    remotive,
    himalayas,
)

# Ім'я в config.yaml -> модуль зі search()
REGISTRY = {
    "djinni": djinni,
    "dou": dou,
    "remoteok": remoteok,
    "weworkremotely": weworkremotely,
    "robota_ua_email": robota_ua_email,
    "work_ua_email": work_ua_email,
    "nofluffjobs": nofluffjobs,
    "justremote": justremote,
    "indeed": indeed,
    "linkedin_email": linkedin_email,
    "remotive": remotive,
    "himalayas": himalayas,
}
