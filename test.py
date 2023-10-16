import logging
from time import sleep
from esm.EsmMain import EsmMain

esm = EsmMain(caller="test")
log = logging.getLogger(__name__)

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")
log.debug(f"debugging is: {esm.config.general.debugMode}")





# this calculation is probably wrong, vermillion says that only the duration stacks, not the effect.
healthpersecond=25
rof=0.25
clipsize=6
effectduration=5
reloadduration=2.5

health = 0
hits = 0
time = 0
looptime = rof
reload = 0
clip = clipsize
stack = []
healthchange = 0
while time < 30:
    print(f"time: {time:6.3f}, health: {health:4.0f}, change: {healthchange:2.0f}, stack size: {len(stack):2}, hits: {hits:2}, reload: {reload:.2f}, clip: {clip}, stack {stack}")

    if clip > 0:
        clip = clip - 1
        hits = hits + 1
        stack.append(time)
    else:
        if reload >= reloadduration:
            clip = clipsize
            reload = 0
        else:
            reload = reload + looptime
    healthchange = healthpersecond * looptime * len(stack)
    health = health + healthchange 
    time = time + looptime
    for effect in stack:
        if time - effect > effectduration:
            stack.remove(effect)
