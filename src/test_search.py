from dotenv import load_dotenv
from Logger import *
from ShodanCrawler import *

load_dotenv()

run_folder = "../results/Minecraft_Server"

crawler = ShodanCrawler(
    result_folder=run_folder,
    verbose=True
)

crawler.crawl("product:minecraft port:25565")