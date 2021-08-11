#!/bin/sh
set -eu

ROUTE_TABLE_PY=/opt/code/localstack/.venv/lib/python3.7/site-packages/moto/ec2/responses/route_tables.py
echo Patching $ROUTE_TABLE_PY
cat << EOF | patch -N $ROUTE_TABLE_PY
--- route_tables.py.orig
+++ route_tables.py
@@ -128,6 +128,7 @@
            {% if route.local %}
            <item>
              <destinationCidrBlock>{{ route.destination_cidr_block }}</destinationCidrBlock>
+             <origin>CreateRouteTable</origin>
              <gatewayId>local</gatewayId>
              <state>active</state>
            </item>
EOF

exec /usr/local/bin/docker-entrypoint.sh "$@"
