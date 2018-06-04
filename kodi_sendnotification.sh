#!/bin/bash
. ~/.libreelec/options.tools

title=$(hostname | tr '[:lower:]' '[:upper:]')
if [ ! -z "$1" ]; then
  msg="$1"
else
  msg="reminder from $(hostname)"
fi

json="{'jsonrpc': '2.0', 'method': 'GUI.ShowNotification', 'id': 1, 'params': {'title': '$title', 'message': '$msg' } }"
curl -G http://$KODI_CLIENT/jsonrpc \
     --data-urlencode "request=${json//\'/\"}" \
     > /dev/null

