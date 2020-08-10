## Benchmarks

This directory contains a shell script to run the benchmarks and a few python helper scripts.

I currently run the benchmarks on a mac laptop with SSD. When I get time, I will dockerize this
to make it easy to run the bench in more environments.

This is what the benchmarks do
- Import 200000 commands from bash history. **This is a lot** - 500 commands per day over 1 year is still < 200k
- log commands via log-recent in 3 batches, 500 per batch. So if each batch takes 50 secs, it
  means log-recent will add a latency of 0.1 secs for each command prompt.
- Run simple recent command 1000 times. So if this takes 150 secs, it means simple recent commands
  roughly take 0.15 secs to query the shell history. Given that I'm importing 200000 commands from "bash history",
  this number will be a reasonable approximation for what a user will notice. It's probably an upper bound.


A more serious benchmark will need do do the following
- Measure the timing for reads/writes when the user stores a lot of environment variables
- Measure the impact of page cache. Currently for the benchmarking I reset the page cache once in
  a while. If I care about this seriously, this is not good enough.
- What if the user does not have the luxury of an SSD? I suspect there will not be much impact, as for most common
  cases, we will hit the page cache. For example, on my laptop 13% of recent.db is in page cache and most "recent"
  results will probably be in the page cache.  
  ```
  (bash) >17:21:49 ~ $ vmtouch -v ~/.recent.db
  [Oo                      o       o  o o oOO] 17/125
  
             Files: 1
       Directories: 0
    Resident Pages: 17/125  68K/500K  13.6%
           Elapsed: 0.000191 seconds

    ```

  
##Results

```
Metric          About                                                Avg  Range
--------------  ------------------------------------------------  ------  -------
import.200000   Importing 200000 commands from bash history         1     1-1
log.500.batch1  Logging 500 commands into recent. batch number 1   34     32-37
log.500.batch2  Logging 500 commands into recent. batch number 2   33.67  31-37
log.500.batch3  Logging 500 commands into recent. batch number 3   32     31-34
query.1000      Querying 1000 commands from recent                119.5   118-121

```