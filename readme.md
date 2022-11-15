## Instructions to Run:
1. Install the Python package dependencies with pip.
2. Install Redis (I'm on Windows, so I used Windows Subsystem for Linux to run the server)
3. Boot up the Redis server
4. Run ```main.py```

## Problem Statement:
Use the Spotify API to get all artists as fast as possible. Need to capture: 'Artist URI', 'Artist Name', 'Genres', 'Popularity'. You may only use one (1) API Token.

## Introduction:
The speed of our program will be limited by the rate limits Spotify imposes on their API. This is based on the token, rather than the IP making the request, so we cannot bypass the rate limit simply by adding proxies.

Of the available endpoints, there are a few options that return lists of artists:
1. Get Several Artists
- This returns artist objects with the URIs we pass to the endpoint. This is clearly not very useful.
2. Search
- Allows us to search artists matching a keyword string, optionally filtering on year, artist, and genre.
- Promising in that it returns up to 50 artists in a single request, however the index of results for a single query stops at 1000.
- It is unclear how to perform a systematic exploration of all artists in the catalog with a set of search criteria.
3. Get Related Artists
- Given an Artist URI, returns a set of related artists.
- Empirically, this set consists of 20 artists, but this is not specified explicitly in the documentation.
- We will primarily use this endpoint, as it provides a clear path forward.

## Definitions:
1. We say that Artist A is 'related' to Artist B if the latter is among the results of calling 'Get Related Artists' on the former.
2. Let G = (V, E) be a directed graph where V is the set of artists in the Spotify catalog. A node v1 is adjacent to a node v2 if and only if v1 is related to v2.

## Assumptions:
1. G is connected, that is, it has a single connected component.
2. G does not change while we run this program.

With these assumptions, the problem statement resembles an online graph exploration problem. In contrast to the typical formulation however, we have the luxury of persistent storage. This allows us to determine whether a node has been previously visited and backtrack to a previous node without having to traverse a path to get there.

To make sure we find every artist, we must 'explore' every node (that is, call 'Get Related Artists' on each artist). Otherwise, we could be foiled by pathological subgraphs, such as 20 artists which very nearly form a clique except for one edge.

Therefore, to find all artists as fast as possible, we simply need to make sure we call the endpoint exactly once for every artist and ensure there is no downtime aside from rate limiting.

Caveat: As explained earlier, the 'Search' endpoint returns more artists in a single request, so we could hypothetically find every artist faster if we explored the entire graph using 'Search'. I don't see a way to do this, sadly.

## Technical Design:

**NOTE:** The Client Credentials authorization workflow used here requires refreshing the token after one hour. To prevent this code from actually being used to scrape the entire artist database, we do not refresh the token automatically, so the get_related_artist requests will all start failing when the token expires.

We explore the graph via breadth first search using parallel processes starting from different nodes. We maintain an LRU cache for quickly identifying whether a node has recently been seen. This is why we opt for breadth-first instead of depth-first. Presumably, if A is related to B and B is related to C, A has a decent chance of being related to C. 

We use a SQL database to store the artists we have explored. We opt for sqlite3, because it is simple, lightweight, and built into Python.

While we are not cut off due to rate limiting we continually send http requests to 'Get Related Artists' from a queue of artists to explore. Because the queue may get quite large, it may not be possible to store the whole thing in memory. Thus, we use a task queue to manage the available tasks. I've opted for redis, because I've been meaning to learn how redis works anyways.

After we explore a node, we check the LRU cache for the adjacent nodes and update the cache. If any are not in the cache, we check for them in the SQL database. If they are not in the database, we add them to the database, then push them to the task queue to be explored later. If we are cut off by rate limiting, we pause the process for however long the Spotify API instructs us to.
