#!/bin/bash
echo "starting..."

printenv > /etc/environment

service cron start

tail -f /dev/null