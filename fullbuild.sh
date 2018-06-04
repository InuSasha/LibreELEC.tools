#!/bin/bash

ARCH_LIST="Generic LePotato Rockchip RPi2 WeTek_Core WeTek_Play"
if [ "$1" == "all" ]; then
  suffix=""
  if [ ! -z "${2}" ]; then
    suffix=".${2}"
  fi
  for i in $ARCH_LIST; do
    screen -S ${i}${suffix} -dm $0
  done
  exit 0
fi

BUILD_NAME=${1}
if [ -z "${BUILD_NAME}" -a ! -z "${STY}" ]; then
  BUILD_NAME=$(cut -d '.' -f 2 <<< $STY)
fi

BUILD_LOG=.work/$BUILD_NAME.log
FAIL_LOG=.work/$BUILD_NAME.fail
cols=100

# ENV by name
case $BUILD_NAME in
  "Generic")    export ARCH=        DEVICE=         PROJECT=;;
  "LePotato")   export ARCH=arm     DEVICE=LePotato PROJECT=Amlogic;;
  "Rockchip")   export ARCH=arm     DEVICE=RK3399   PROJECT=Rockchip;;
  "RPi2")       export ARCH=arm     DEVICE=RPi2     PROJECT=RPi;;
  "RPi")        export ARCH=arm     DEVICE=RPi      PROJECT=RPi;;
  "WeTek_Core") export ARCH=arm     DEVICE=         PROJECT=WeTek_Core;;
  "WeTek_Play") export ARCH=arm     DEVICE=         PROJECT=WeTek_Play;;
esac

# get all addon packages
IFS="
"
export IFS
addons=$(
  find packages projects/*/packages -name 'package.mk' \
    | xargs grep 'PKG_IS_ADDON="yes"' \
    | sed 's|/package.mk:.*$||;s|^.*/||g' \
    | sort -u
)

# prepare build
mkdir -p .work
rm -f $BUILD_LOG $FAIL_LOG

# make the image build
( make
  if [ $? == 0 ]; then
    printf "##### OK IMAGE $(printf '#%.0s' {1..${cols}})\n" | cut -c 1-${cols}
  else
    printf "##### FAIL IMAGE $(printf '#%.0s' {1..${cols}})\n" | cut -c 1-${cols}
    echo image >> $FAIL_LOG
  fi
) 2>&1 \
  | tee -a $BUILD_LOG

# make addons
for addon in $addons; do
  printf "##### $addon $(printf '#%.0s' {1..${cols}})\n" | cut -c 1-${cols}

  # build addon
  ./scripts/create_addon $addon
  ret=$?

  # check return
  if [ $ret == 0 ]; then
    printf "##### OK $addon $(printf '#%.0s' {1..${cols}})\n" | cut -c 1-${cols}
  else
    printf "##### FAIL $addon $(printf '#%.0s' {1..${cols}})\n" | cut -c 1-${cols}
    echo $addon >> $FAIL_LOG
  fi
done \
  2>&1 \
  | tee -a $BUILD_LOG

