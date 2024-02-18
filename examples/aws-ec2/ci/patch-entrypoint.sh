#!/bin/sh
set -eu

curl -sfL https://busybox.net/downloads/binaries/1.35.0-x86_64-linux-musl/busybox -o /usr/local/bin/busybox
chmod a+x /usr/local/bin/busybox

ROUTE_TABLE_PY=/opt/code/localstack/.venv/lib/python3.11/site-packages/moto/ec2/responses/route_tables.py
echo Patching $ROUTE_TABLE_PY
cat << EOF | busybox patch -N $ROUTE_TABLE_PY
--- /opt/code/localstack/.venv/lib/python3.11/site-packages/moto/ec2/responses/route_tables.py.orig	2024-02-18 23:06:26.221594278 +0000
+++ /opt/code/localstack/.venv/lib/python3.11/site-packages/moto/ec2/responses/route_tables.py	2024-02-18 23:09:37.329354492 +0000
@@ -162,6 +162,7 @@
               {% if route.destination_prefix_list_id %}
                 <destinationPrefixListId>{{ route.destination_prefix_list_id }}</destinationPrefixListId>
               {% endif %}
+             <origin>CreateRouteTable</origin>
              <gatewayId>local</gatewayId>
              <state>active</state>
            </item>
EOF

exec /usr/local/bin/docker-entrypoint.sh "$@"
