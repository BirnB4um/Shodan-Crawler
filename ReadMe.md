This is a Search-Crawler for the Shodan API.  
It exploits a bug (or feature?) in the API to make infinite requests for free.  
This works because the API doesn't charge any credits if the number of results for a request is lower than the limit per page (100).  

Is it a bug or a feature? I would love to know.

### Using the Crawler
You need a API key to use it.  
Either you purchase one or request a academic account for free if you are a student/researcher.

### Note:  
There are two caveats:  
1) With the default rate limiting delays a search over the entire internet takes around a day.
2) There seems to be a mismatch between the number of total results and the actual number of results. In my tests i only got around 60% of the reported number of results. This may be a caching problem or just a side effect of this conquer and divide approach.  