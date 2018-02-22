=========================
Redis to websocket logger
=========================

```
+------------+            +-----+
|  Producer  | +--------> |Redis|
+------------+            +--+--+
                             |
                             |
       +-------+             |             +---------+
       |logfile| <-----------+-----------> |websocket|
       +---+---+                           +---+-----+
           |                                   ^
           |                                   |
           +-----------------------------------+
```

Server
======
```
pip3 install wslogtail
mkdir ~/wslogtail
wslogtail --logdir ~/wslogtail
```

Producer
========
```
redis-cli publish wslogger:log.name "bonjour, monde cruel"
```

Web client
==========
```
<!doctype html>
<html>
  <head>
    <script>
    var con = new WebSocket("ws://localhost:8756/log.name");
    con.onerror = function(error) {
        console.log("err", error);
    };
    con.onmessage = function(e) {
        console.log("received", JSON.parse(e.data)["line"]);
    };
    </script>
  </head>
  <body>
    <p>Watch your console.</p>
  </body>
</html>
```