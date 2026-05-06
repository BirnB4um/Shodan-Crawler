import sys
import os
import time
from ShodanCrawler import ShodanCrawler
from Logger import get_logger

base_folder = "/opt/shodan-crawler"
data_folder = os.path.join(base_folder, "data")


logger = get_logger("script", data_folder)



def minecraft_crawl():
    logger.info("Starting Minecraft crawl")
    start_time = time.time()
    
    run_name = "minecraft"
    run_folder = os.path.join(data_folder, run_name)
    
    try:
        crawler = ShodanCrawler(
            result_folder=run_folder,
            verbose=False
        )

        crawler.crawl("product:minecraft port:25565", from_beginning=True)
    except Exception as e:
        logger.error(f"Error during Minecraft crawl: {str(e)}", exc_info=True)

    logger.info(f"Finished Minecraft crawl (took {round((time.time() - start_time)/60, 1)} minutes)")


def hytale_crawl():
    logger.info("Starting Hytale crawl")
    start_time = time.time()
    
    run_name = "hytale"
    run_folder = os.path.join(data_folder, run_name)
    
    try:
        crawler = ShodanCrawler(
            result_folder=run_folder,
            verbose=False
        )

        crawler.crawl("product:hytale", from_beginning=True)
    except Exception as e:
        logger.error(f"Error during Hytale crawl: {str(e)}", exc_info=True)

    logger.info(f"Finished Hytale crawl (took {round((time.time() - start_time)/60, 1)} minutes)")

logger.info("Starting script")

crawl_active_file = os.path.join(data_folder, "crawl_active")
if os.path.isfile(crawl_active_file):
    logger.warning("Previous crawl is still active. Skipping this one.")
    sys.exit(0)
    
with open(crawl_active_file, "w") as file:
    pass


minecraft_crawl()
hytale_crawl()


if os.path.isfile(crawl_active_file):
    os.remove(crawl_active_file)

logger.info(f"Finished script")