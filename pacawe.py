#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Description: A flexible Python pacman notifier.
# Usage: Put shell script with command 'pacman -Sy' into /etc/cron.hourly/
# Author: sabooky <sabooky@yahoo.com>
# Special Thanks for the orginal idea/script: Michal Orlik <thror.fw@gmail.com>

from __future__ import print_function

#===============================================================================
# SETTINGS
#===============================================================================
#-------------------------------------------------------------------------------
# PACKAGE RATING - prioritize packages by rating
#-------------------------------------------------------------------------------
# pkgs will be sorted by rating. pkg rating = ratePkg + rateRepo for that pkg
# pkg (default=0, wildcards accepted)
ratePkg = {
        'kernel*':10,
        'pacman':9,
        'nvidia*':8,
        }
# repo (default=0, wildcards accepted)
rateRepo = {
        'core':5,
        'extra':4,
        'community':3,
        'testing':2,
        'unstable':1,
        }
# at what point is a pkg considered "important"
iThresh = 5
#-------------------------------------------------------------------------------
# OUTPUT SETINGS - configure the output format
#-------------------------------------------------------------------------------
# show the individual package detail (True/False)
showPkgDetail = True
# show the summary line (True/False)
showSummary = True
# number of packages to display (None = display all)
num_of_pkgs = None
# change width of output
width = 52

# formula to use to calculate the size variable. input=size in bytes
calc_size = lambda size: size/1024/1024

# separator between lines
separator = "\n"
# pkg template - this is how individual pkg info is displayed ('' = disabled)
# valid keywords - lowercase version of all % surrounded values in desc files
# see: /var/lib/pacman/sync/*/*/desc for more info
# also available is a special variable "size" which is defined above
# regular pkgs
pkgLeftColTemplate = " {repo}/{name} {version}"
pkgRightColTemplate = "{size:.2f} MB"
# important pkgs
ipkgLeftColTemplate = " *!*" + pkgLeftColTemplate
ipkgRightColTemplate = pkgRightColTemplate
# pkg template
# valid keywords - leftCol, rightCol, width, pad
# width = total width, pad = width - leftCol
pkgTemplate = "{leftCol}{rightCol:>{pad}}"
ipkgTemplate = pkgTemplate
# offset, this is a good way of getting around non-printable characters
pkgOffset = 0
ipkgOffset = 0

# summary template - this is the summary line at the end
# valid keywords - numpkg, size, inumpkg, isize, pkgstring
summaryLeftColTemplate = " {numpkg} {pkgstring}"
summaryRightColTemplate = "{size:.2f} MB"
# important summary template - same as above if "important" pkgs are found
isummaryLeftColTemplate = summaryLeftColTemplate + " ({inumpkg} important {isize:.2f} MB)"
isummaryRightColTemplate = summaryRightColTemplate
# summary template
# valid keywords - leftCol, rightCol, width, pad
# width = total width, pad = width - leftCol
summaryTemplate = "{leftCol}{rightCol:>{pad}}"
isummaryTemplate = summaryTemplate

# separator before summary ('' = disabled)
block = ('-' * 12).rjust(width)
# up to date msg
u2d = ' Your system is up-to-date'
# package string messages
pkg_string = 'package'
pkgs_string = 'packages'
# translate table, the output is run through this and translated
# each entry is a tuple (key, value, count) pair
# key: regex to search for
# value: replacement string (can use \1 for groups)
# count: number of times to do the replacement (on a given column), NONE/0 for all
Xlate = ()
#Xlate = ((r"(e)", r"(\1)", 0),
#        )


import subprocess
import sys

from glob import glob
from fnmatch import fnmatch
from re import sub


#===============================================================================
# Functions
#===============================================================================
def get_pkgs():
    """runs pacman -Qu parsing the out of date package list"""
    p = subprocess.Popen(['pacman','-Qu'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    data = p.communicate()[0]
    data_split = data.split('\n\n')
    if len(data_split) < 3:
        return []
    targets_str = data_split[-2]
    pkgs_str = targets_str.split(':')[1]
    packages = [entry.split()[0] for entry in pkgs_str.split('  ') if entry.strip()]
    return packages


def get_pkg_info(pkg_name, calc_size = lambda size: size/1024/1024, iThresh = 5):
    """Gets the arch linux package info by parsing the desc file.
    pkg_name: the name of the package
    calc_size: function to calculate size, takes bytes as input
    iThresh: at what point is the package considered important"""
    desc_paths = glob('/var/lib/pacman/sync/*/%s'%pkg_name)
    if not desc_paths:
        return None
    pkg_desc_fname = desc_paths[0] + '/desc'
    
    pkg_info = {}
    pkg_info['repo'] = pkg_desc_fname.split('/')[-3]
    with open(pkg_desc_fname) as f:
        for line in f:
            line = line.strip()
            if line.startswith('%') and line.endswith('%'):
                name = line.strip('%').lower()
                value = f.next().strip()
                pkg_info[name] = value

    # size converted using user settings
    pkg_info['size'] = calc_size(float(pkg_info['csize']))

    pkg_rate = [v for x, v  in ratePkg.items() 
            if fnmatch(pkg_info['name'], x)]
    repo_rate = [v for x, v in rateRepo.items()
            if fnmatch(pkg_info['repo'], x)]
    pkg_info['rate'] = sum(pkg_rate + repo_rate)

    # am i important?
    pkg_info['important'] = pkg_info['rate'] >= iThresh

    return pkg_info


def format_line(left_template, right_template, join_template, data, width, offset=0, Xlate=()):
    """Helper function to print each output line
    left_template: this is the left side, will be cropped to fit width/offset.
    right_template: the right half of the template
    join_template: the full template, this can join left/right_templates or be standalone.
                   this template gets passed in the width and the padding to allow for
                   right alignment of the right_template
    data: the pkg data
    width: maximum width of line
    offset: offset for cropping right template width, helpful for non printable chars
            example: <span color='red'>{name}
            -18 offset would make it so that line gets cropped properly
    Xlate: any post formatting translations."""
    line_left = left_template.format(**data)
    line_right = right_template.format(**data)
    for k, v, c in Xlate:
        line_left = sub(k, v, line_left, c)
        line_right = sub(k, v, line_right, c)

    line = join_template.format(leftCol=line_left,
            rightCol=line_right,
            width=width, pad=0)

    # if the line is longer than width, crop left col
    line_len = len(line) + offset
    if width and line_len>width:
        line_left = line_left[:width - len(line_right)-4] + '...'
    pad = width - len(line_left)

    line = join_template.format(leftCol=line_left,
            rightCol=line_right,
            width=width, pad=pad)
    return line


#===============================================================================
# Main Program
#===============================================================================
# if config file is supplied parse it
if len(sys.argv) == 2:
    execfile(sys.argv[1])
# parse pacman output and get a list of pkg names/info
pkg_names = get_pkgs()
pkgs = []
for pkg_name in pkg_names:
    pkg = get_pkg_info(pkg_name, calc_size=calc_size)
    if not pkg:
        print("WARNING: %s not found, skipping" % pkg_name, file=sys.stderr)
        continue
    pkgs.append(pkg)

# out-of-date packages found, get summary info, format lines and print
if pkgs:
    # get general summary information
    summary = {}
    summary['numpkg'] = len(pkgs)
    summary['size'] = sum([x['size'] for x in pkgs])
    if summary['numpkg'] == 1:
        summary['pkgstring'] = pkg_string
    else:
        summary['pkgstring'] = pkgs_string
    summary['inumpkg'] = 0
    summary['isize'] = 0
    # process each package into lines
    lines = []
    pkgs.sort(key=lambda x: (x['rate'], x['size']), reverse=True)
    for pkg in pkgs:
        if pkg['rate'] >= iThresh:
            summary['isize'] += pkg['size']
            summary['inumpkg'] += 1
            left_template = ipkgLeftColTemplate
            right_template = ipkgRightColTemplate
            pkg_template = ipkgTemplate
            offset = ipkgOffset
        else:
            left_template = pkgLeftColTemplate
            right_template = pkgRightColTemplate
            pkg_template = pkgTemplate
            offset = pkgOffset
        line = format_line(left_template, right_template, pkg_template, pkg, width, offset, Xlate)
        lines.append(line)
    # process summary line
    if summary['inumpkg']:
        left_template = isummaryLeftColTemplate
        right_template = isummaryRightColTemplate
        summary_template = isummaryTemplate
    else:
        left_template = summaryLeftColTemplate
        right_template = summaryRightColTemplate
        summary_template = summaryTemplate
    summary_line = format_line(left_template, right_template, summary_template, summary, width, Xlate=Xlate)
    # create and print output based on user options
    out_list = []
    if showPkgDetail:
        out_list += lines[:num_of_pkgs]
    if block:
        out_list.append(block)
    if showSummary:
        out_list.append(summary_line)
    print(*out_list, sep=separator)
else:
    print(u2d)
