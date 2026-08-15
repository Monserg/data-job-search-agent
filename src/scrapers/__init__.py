from . import (
    djinni,
    dou,
    remoteok,
    weworkremotely,
    robota_ua,
    work_ua,
    nofluffjobs,
    justremote,
    indeed,
    linkedin_alerts,
)

# Ім'я в config.yaml -> модуль зі search()
REGISTRY = {
    "djinni": djinni,
    "dou": dou,
    "remoteok": remoteok,
    "weworkremotely": weworkremotely,
    "robota_ua": robota_ua,
    "work_ua": work_ua,
    "nofluffjobs": nofluffjobs,
    "justremote": justremote,
    "indeed": indeed,
    "linkedin_alerts": linkedin_alerts,
}
