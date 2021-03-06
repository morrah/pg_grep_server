# About

**[pg_grep_client](https://github.com/morrah/pg_grep_client)** parses postgres log files using regexp and pushes it's contents to redis channels, using ip as a channel name;  
**[pg_grep_server](https://github.com/morrah/pg_grep_server)** subscribes web-clients to channels.

![screenshot](https://files.catbox.moe/pbjdyt.png "screenshot")  
[demo.mp4 (4.5Mb)](https://files.catbox.moe/wkly9h.mp4)

# Installation

```
sudo apt-get install virtualenv python3.5 python3.5-dev redis-server
virtualenv -p python3.5 pg_grep_server_env
source pg_grep_server_env/bin/activate
git clone https://github.com/morrah/pg_grep_server.git && cd pg_grep_server
pip install -r requirements.txt
python server.py
```

# TODO

async incoming websocket messages while redis channels reading;  
move web-server ip:port and redis ip:port to conf file;  
websockets fallback for old-browsers;  
get rid off javascript global vars.
