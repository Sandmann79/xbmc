#!/bin/bash
openbox &
/usr/bin/firefox "$@"
kill %1
