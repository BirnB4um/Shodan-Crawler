
import shodan
import os
import json
import time
import ipaddress
import sqlite3
from Logger import get_logger


class ShodanCrawler:

    def __init__(
            self,
            result_folder:str,
            api_count_delay:float=5,
            api_search_delay:float=5, 
            max_results:int=90, 
            save_interval:int=1000,
            api_retries:int=5,
            verbose:bool=False,
            result_processor=None,
            ):
        """
        Init Shodan Crawler.  
        Requires SHODAN_API_KEY environment variable to be set.  
        
        **Note**: This class is not thread-safe. Only one instance should be used per process.  
        
        :param result_folder: Folder to save results, bitstack and log.
        :type result_folder: str
        
        :param api_count_delay: Base delay between API count requests in seconds.
        :type api_count_delay: float
        
        :param api_search_delay: Base delay between API search requests in seconds.
        :type api_search_delay: float
        
        :param max_results: Maximum number of accepted results per query. Should be less than Shodan API limit of 100 to prevent accidental credit consumption.
        :type max_results: int
        
        :param save_interval: Interval to save bitstack to file. (1000 corresponds to ~ 45 minutes)
        :type save_interval: int
        
        :param api_retries: Number of retries for API requests. (default: 5)
        :type api_retries: int
        
        :param verbose: If True, enables detailed logging.
        :type verbose: bool
        
        :param result_processor: Function to preprocess results before saving to DB. Should take one result as input and return the processed result.  
        :type result_processor: function
        """
        
        self.result_folder = result_folder
        os.makedirs(self.result_folder, exist_ok=True)
        self.bitstack_file = os.path.join(self.result_folder, "bitstack")
        self.result_file = os.path.join(self.result_folder, "result.db")
        
        self.logger = get_logger("shodan", folder=os.path.join(self.result_folder, "log"))

        self.sql_connection = None
        self.sql_cursor = None
        
        self.api = shodan.Shodan(key=os.getenv("SHODAN_API_KEY"))
        self.api_count_delay = api_count_delay
        self.api_search_delay = api_search_delay
        self.max_results = max_results
        self.save_interval = save_interval
        self.api_retries = api_retries
        
        self.verbose = verbose
        
        self.result_processor = result_processor
        
        self.bitstack = []


    def _save_bitstack(self, filepath:str, bitstack:list[int]=None):
        """
        Save bitstack to file.
        If bitstack is None, saves self.bitstack.
        """
        
        if self.verbose:
            self.logger.info("Saving bitstack")
        with open(filepath, "w") as file:
            if bitstack is None:
                bitstack = self.bitstack
            bitstack_str = "".join([str(bit) for bit in bitstack])
            file.write(bitstack_str)


    def _load_bitstack(self, filepath:str):
        """
        Load bitstack from file.
        """
        
        if self.verbose:
            self.logger.info("Loading bitstack")
        if os.path.isfile(filepath):
            with open(filepath, "r") as file:
                bitstack_str = file.read()
                self.bitstack = [int(bit) for bit in bitstack_str if bit in ["0","1"]]
        else:
            self.bitstack = [0]


    def _get_counts(self, query:str):
        """
        Returns number of results for a given query.
        Returns -1 if error occured.
        """
    
        for t in range(self.api_retries):
            try:
                time.sleep(self.api_count_delay * 2**t)
                result = self.api.count(query=query)
                if isinstance(result, str):
                    self.logger.info(f"API count: {query}")
                    self.logger.error(f"count API returned string instead of dict.\n{result}")
                    return 999999

                num_results = result.get("total", -1)
                if self.verbose:
                    self.logger.info(f"API count: {query} ({num_results})")
                if num_results == -1:
                    self.logger.error(f"count API returned -1 total results.\n{json.dumps(result, indent=4)}")
                return num_results
            except Exception as e:
                self.logger.info(f"API count: {query}")
                self.logger.error(f"{str(e)}", exc_info=True)

        raise RuntimeError("Too many tries for count API.")
    

    def _save_results(self, results:list):
        """
        Save collected results.
        """
        
        if len(results) == 0:
            return

        if not (self.sql_connection and self.sql_cursor):
            self.logger.error("No SQL connection")
            return
        
        # preprocess results
        if self.result_processor:
            processed_results = []
            for result in results:
                try:
                    processed_result = self.result_processor(result)
                    if processed_result is not None:
                        processed_results.append(processed_result)
                except Exception as e:
                    self.logger.warning(f"Error while processing result: {str(e)}", exc_info=True)
                    continue
            results = processed_results

        entries = []
        for result in results:
            try:
                ip = result.get("ip_str")
                if not ip:
                    continue

                result.pop("ip_str", None)
                data = json.dumps(result)
                entries.append((ip, data))
            except Exception as e:
                self.logger.warning(f"Error while parsing result: {str(e)}", exc_info=True)
                continue

        if self.verbose:
            self.logger.info(f"Saving {len(entries)} results")

        try:
            self.sql_cursor.executemany(
                """
                INSERT INTO results (ip, data)
                VALUES (?, ?)
                ON CONFLICT(ip) DO UPDATE SET
                    data = excluded.data;
                """, 
                entries
            )
            self.sql_connection.commit()
        except Exception as e:
            self.logger.error(f"Error while saving results to DB: {str(e)}", exc_info=True)
            self.sql_connection.rollback()


    def _collect_results(self, query:str):

        for t in range(self.api_retries):
            try:
                results = self.api.search(query=query, minify=False)

                if isinstance(results, str):
                    self.logger.info(f"API search: {query}")
                    self.logger.error(f"API search returned string instead of dict.\n{results}")
                    time.sleep(self.api_search_delay)
                    return
                
                matches = results.get("matches", [])
                if self.verbose:
                    self.logger.info(f"API search: {query} => ({len(matches)})")
                    if len(matches) != results.get("total", -1):
                        self.logger.warning(f"num matches doesn't align with total results. {len(matches)}/{results.get('total')}")
                self._save_results(results=matches)
                time.sleep(self.api_search_delay)
                return
            except Exception as e:
                self.logger.info(f"API search: {query}")
                self.logger.error(f"{str(e)}", exc_info=True)
                time.sleep(self.api_search_delay * 2**t)

        self.logger.error(f"Failed to collect results for query: {query}")
        raise RuntimeError("Too many tries for search API.")


    def _get_network_range(self, bitstack:list[int]=[]):
        """
        Convert bit stack to network range in CIDR notation.
        """
        
        if not bitstack:
            return ""

        assert len(bitstack) <= 32, f"Bit stack exceeds maximum length of 32"
        assert all(0 <= bit <= 1 for bit in bitstack), f"bitstack can only contain values 0 and 1"

        stack_size = len(bitstack)
        ip_numbers = []
        temp = 0

        for stack_idx, bit in enumerate(bitstack):
            offset = 7 - (stack_idx % 8)  # 7-0
            temp += bit * 2**offset
            if offset == 0 or stack_idx == stack_size - 1:
                ip_numbers.append(temp)
                temp = 0

        ip_numbers.extend([0 for i in range(4-len(ip_numbers))])

        ip_address = ".".join([str(n) for n in ip_numbers])
        if stack_size < 32:
            ip_address += "/" + str(stack_size)

        return ip_address


    def _form_query(self, query:str, bitstack:list[int]=None):
        """
        Create final query by appending net filter to base query.  
        If bitstack is None, uses self.bitstack.
        """
        bitstack = self.bitstack if bitstack is None else bitstack
        net_range = self._get_network_range(bitstack)
        if not net_range:
            return query
        
        return query + " net:" + net_range


    def _is_global_ip(self, bitstack:list[int]) -> bool:
        ip = self._get_network_range(bitstack or [0])

        if ip.startswith("10.") or ip.startswith("192.168."):
                return False

        ip = ipaddress.ip_network(ip, strict=False)

        idx_1, idx_2 = None, None

        for i, net in enumerate(ipaddress._IPv4Constants._private_networks):
            if ip.network_address in net:
                idx_1 = i
                break

        for i, net in enumerate(ipaddress._IPv4Constants._private_networks):
            if ip.broadcast_address in net:
                idx_2 = i
                break

        if idx_1 is not None and \
            idx_2 is not None and \
            idx_1 == idx_2:
            return False
        return True


    def _init_sql(self):
        if not (self.sql_connection and self.sql_cursor):
            self.logger.error("Error in init SQL: No SQL connection.")
            return

        self.sql_cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT UNIQUE NOT NULL,
                data TEXT DEFAULT '{}'
            )
            """
        )

        self.sql_connection.commit()



    def _goto_next_node(self):
        """
        Moves bitstack to next node in the tree.  
        If last bit is 0, set to 1, else pop last bit.  
        This function directly modifies self.bitstack.  
        At the end self.bitstack may be empty.  
        """
        
        while True:
            if len(self.bitstack) == 0:
                return
            
            if self.bitstack[-1] == 0:
                self.bitstack[-1] = 1
                return
            else:
                self.bitstack.pop()


    def _crawl_iteration(self, query:str):
        """
        Crawl generator.  
        Starts the search given a query.  
        """

        while True:
                
            # check if done
            if len(self.bitstack) == 0:
                return
            
            if len(self.bitstack) > 32:
                self.logger.error(f"Bitstack exceeds maximum length of 32: {self.bitstack}")
                self._goto_next_node()
                continue


            # check if in global ip space
            if not self._is_global_ip(self.bitstack):
                self._goto_next_node()
                continue


            # check total results
            final_query = self._form_query(query, self.bitstack)
            result_count = self._get_counts(final_query)
            
            if result_count == -1:
                self.logger.error(f"Result count was -1 for bitstack: {self.bitstack}")
                self._goto_next_node()
            
            # if too many results, go deeper
            elif result_count > self.max_results:
                self.bitstack.append(0)
            
            # if acceptable result count, collect results
            else:
                if result_count > 0:
                    self._collect_results(final_query)
                self._goto_next_node()
                
            yield
            


    def crawl(self, query:str, from_beginning:bool=False):
        """
        Start crawling with given base query.  
        The query should not use the 'net' filter, although it would still work.
        
        :param query: Base Shodan query to crawl.
        :type query: str
        :param from_beginning: If True, starts a new crawl and ignores existing bitstack file.
        :type from_beginning: bool
        """
        
        os.makedirs(self.result_folder, exist_ok=True)
        
        if os.path.isfile(self.bitstack_file) and not from_beginning:
            self._load_bitstack(self.bitstack_file)
            self.logger.info(f"Resuming from bitstack of length {len(self.bitstack)} -> {''.join(map(str, self.bitstack))}")
            
        else:
            self.bitstack = [0]
            self.logger.info(f"Starting new crawl")
            

        with sqlite3.connect(self.result_file) as conn:
            self.sql_connection = conn
            self.sql_cursor = conn.cursor()
            self._init_sql()

            for t in range(3):
                try:
                    for i, data in enumerate(self._crawl_iteration(query), start=1):
                        if i % self.save_interval == 0:
                            self._save_bitstack(self.bitstack_file)
                    break
                except Exception as e:
                    self.logger.error(f"Error while crawling: {str(e)} (Try {t+1}/3)", exc_info=True)

            self.sql_connection = None
            self.sql_cursor = None

        if os.path.isfile(self.bitstack_file):
            os.remove(self.bitstack_file)
            
        self.logger.info("Finished crawl.")

