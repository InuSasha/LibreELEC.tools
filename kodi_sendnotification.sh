#!/bin/bash
. $(dirname $0)/options.txt

title=$(hostname | tr '[:lower:]' '[:upper:]')
msg="build done"
json="{'jsonrpc': '2.0', 'method': 'GUI.ShowNotification', 'id': 1, 'params': {'title': '$title', 'message': '$msg' } }"
curl -G http://$KODI_CLIENT/jsonrpc \
     --data-urlencode "request=${json//\'/\"}" \
     > /dev/null

