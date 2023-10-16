import logging
import click

#from esm import EsmMain
from esm.EsmMain import EsmMain

log = logging.getLogger(__name__)

@click.command()
def ramdiskPrepare(esm: EsmMain):
    esm.ramdiskManager.prepare()

######################################################
## main code start
######################################################
# initialize config and logging
esm = EsmMain(caller=__file__,
            configFileName="esm-config.yaml"
            )

log.debug("Start of script")
log.debug(f"Logging to: {esm.logFile}")


log.info(f"Script finished successfully. Check the logfile ({esm.logFile}) if you missed something. Bye!")
