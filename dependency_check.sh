#!/bin/bash -e

abort=no
param_use_old=no
while [ $# -gt 0 ]; do
    case $1 in
        '-o'|'--old') 
            param_use_old=yes
            ;;
        *)
            echo "Unknown paramter: $1"
            abort=yes
    esac

    shift
done
if [ "${abort}" == "yes" ]; then
    exit 1
fi

# functions
. ./config/functions
verify_addon() {
  if [ -n "${PKG_ARCH}" ]; then
    VERIFY_FAIL="Incompatible arch: \"${TARGET_ARCH}\" not in [ ${PKG_ARCH} ]"
    listcontains "${PKG_ARCH}" "!${TARGET_ARCH}" && return 1
    listcontains "${PKG_ARCH}" "${TARGET_ARCH}" || listcontains "${PKG_ARCH}" "any" || return 1
  fi

  if [ -n "${PKG_ADDON_PROJECTS}" ]; then
    [ "${DEVICE}" = "RPi" ] && _DEVICE="RPi1" || _DEVICE="${DEVICE}"

    VERIFY_FAIL="Incompatible project or device: \"${_DEVICE:-${PROJECT}}\" not in [ ${PKG_ADDON_PROJECTS} ]"

    if listcontains "${PKG_ADDON_PROJECTS}" "!${_DEVICE:-${PROJECT}}" ||
       listcontains "${PKG_ADDON_PROJECTS}" "!${PROJECT}"; then
      return 1
    fi

    if ! listcontains "${PKG_ADDON_PROJECTS}" "${_DEVICE:-${PROJECT}}" &&
       ! listcontains "${PKG_ADDON_PROJECTS}" "${PROJECT}" &&
       ! listcontains "${PKG_ADDON_PROJECTS}" "any"; then
      return 1
    fi
  fi

  return 0
}
get_addons() {
  local paths filter
  local pkgpath exited
  local count=0 validpkg

  . config/options ""

  case ${1} in
    binary)   paths="^${ROOT}/packages/mediacenter/kodi-binary-addons/";;
    official) paths="^${ROOT}/packages/addons/";;
    all)      paths="^${ROOT}/packages/|^${ROOT}/projects/.*/packages/";;
    *)        paths="^${ROOT}/packages/|^${ROOT}/projects/.*/packages/"; filter="${1}";;
  esac

  exit() { exited=1; }

  for pkgpath in $(cat "${_CACHE_PACKAGE_LOCAL}" "${_CACHE_PACKAGE_GLOBAL}" | grep -E "${paths}"); do
    if [ -n "${filter}" ]; then
      [[ ${pkgpath} =~ ^.*/${filter}@?+?@ ]] || continue
    fi

    exited=0
    source_package "${pkgpath%%@*}/package.mk" &>/dev/null
    [ ${exited} -eq 1 ] && continue

    validpkg="no"
    VERIFY_FAIL=
    # Should only build embedded addons when they are explictly specified in the addon list
    if [ "${PKG_IS_ADDON}" = "embedded" ]; then
      if [ -n "${filter}" ]; then
        verify_addon && validpkg="yes"
      fi
    elif [ "${PKG_IS_ADDON}" = "yes" ]; then
      verify_addon && validpkg="yes"
    fi

    if [ "${validpkg}" = "yes" ]; then
      echo "${PKG_NAME}"
      count=$((count + 1))
    elif [ -n "${VERIFY_FAIL}" -a -n "${filter}" ]; then
      echo "$(print_color CLR_ERROR "${PKG_NAME}"): ${VERIFY_FAIL}" >&2
    fi
  done

  unset -f exit

  if [ ${count} -eq 0 -a -n "${filter}" ]; then
    echo  "$(print_color CLR_ERROR "ERROR: no addons matched for filter ${filter}")" >&2
    echo  "For more information type: ./scripts/create_addon --help" >&2
    die
  fi
}

# list of addiontinal start points
start_points="kodi linux mesa libbX11 toolchain go:host toolchain:host automake:host gettext:host"

mkdir -p .work
exec_path="$(dirname $0)"
build_dir=$(. ./config/options ""; basename ${BUILD})
dep_file=".work/dependency.${build_dir}.csv"
rm -rf ${build_dir}
if [ "${param_use_old}" == "no" ]; then
    rm -rf start.*.${build_dir} fail.*.${build_dir} ${dep_file}
fi

# make plan
if [ "${param_use_old}" == "no" ]; then
    package_list="image $(get_addons all)"
    #package_list="toolchain:host"
    ./tools/viewplan ${package_list} \
        | ${exec_path}/dependency_plan.py \
        | sort -rn \
        > ${dep_file}
fi

while true; do
    package=$(head -n1 ${dep_file} | cut -d',' -f2)
    if [ -z "${package}" ]; then
        break
    fi
    rm -rf ${build_dir}

    start_point_used=none
    deps=$(grep -m1 -e "^[^,]*,${package}," ${dep_file} | cut -d',' -f3)
    for start_point in ${start_points}; do
        if listcontains "${deps}" ${start_point} ; then
            echo "Use start-point: ${start_point}" >&2
            cp -a --reflink=auto start.${start_point}.${build_dir} ${build_dir}
            start_point_used=${start_point}
            break
        fi
    done

    while true; do
        if ! ./scripts/build_mt "${package}" ; then
            rm -rf fail.${package}.${build_dir}
            mv ${build_dir} fail.${package}.${build_dir}
            grep -e "[ ,]${package}[ ,]" ${dep_file} >> ${dep_file}.fail
            sed "/[ ,]${package}[ ,]/d" -i ${dep_file}
            break
        fi
        
        if listcontains "${start_points}" "${package}" && [ ! -e start.${package}.${build_dir} ]; then
            echo "Store start-point: ${package}" >&2
            cp -a --reflink=auto ${build_dir} start.${package}.${build_dir}
            start_point_used=${package}
        fi
        
        sed "/^[^,]*,${package},/d" -i ${dep_file}
        package=$(grep -m1 -e ",\([^,]* \)\?${package}\( [^,]*\)\?*$" ${dep_file} | cut -d, -f2)
        
        deps=$(grep -m1 -e "^[^,]*,${package}," ${dep_file} | cut -d',' -f3)
        for start_point in ${start_points}; do
            if [ -e start.${start_point}.${build_dir} ]; then
                if [ "${start_point_used}" == "${start_point}" ]; then
                    break;
                fi
                if listcontains "${deps}" ${start_point} ; then
                    echo "Do not pass existing start point: ${start_point}" >&2
                    break 2
                fi
            fi
        done

        if [ -z "${package}" ]; then
            break
        fi
    done
done
