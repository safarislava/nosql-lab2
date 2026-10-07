#!/bin/bash
# Sourced by basho riak-cluster.sh before riak start.
echo "WAIT_FOR_ERLANG=60" >> /etc/default/riak

# Clean up stale Bitcask locks from unclean shutdowns/restarts
find /var/lib/riak/bitcask -name "*.lock" -delete 2>/dev/null || true

cat <<EOF > /etc/riak/user.conf
nodename = riak@127.0.0.1
listener.protobuf.internal = 0.0.0.0:8087
listener.http.internal = 0.0.0.0:8098
EOF
