#!/usr/bin/env python3

from os import environ, makedirs, chdir, listdir, rename
from os.path import isdir
from subprocess import call, check_call
from shutil import *
from multiprocessing import cpu_count
from datetime import datetime
from sys import stdout

site = environ['GLUON_SITE']
release = environ['GLUON_RELEASE']
branch = environ['GLUON_BRANCH']
broken = environ['GLUON_BROKEN']

home = '/usr/src/build'

gluondir = '%s/gluon' % home

outdir = '%s/output/%s' % (home, release)
logdir = '%s/log' % outdir

siteconf = '/usr/src/site.conf'
sitemk = '/usr/src/site.mk'
i18ndir = '/usr/src/i18n'

factorydir = '%s/images/factory' % outdir
sysupdir = '%s/images/sysupgrade' % outdir
modulesdir = '%s/modules' % outdir

makedirs(factorydir)
makedirs(sysupdir)
makedirs(modulesdir)
makedirs(logdir)

start = datetime.now()

def format_duration(d):
    s = d.total_seconds()
    return '%.2dh%.2dm%06.3fs' % (s//3600, (s//60)%60, s%60)

# Clone Gluon
if isdir(gluondir):
    rmtree(gluondir)

print('Cloning Gluon... ', end=''); stdout.flush()
with open('%s/git.log' % logdir, 'w') as log:
    check_call('git clone https://github.com/freifunk-gluon/gluon.git %s -b "%s"' % (gluondir, environ['GLUON_TAG']), stdout=log, stderr=log, shell=True)
print('OK'); stdout.flush()

# Add site configuration
sitedir = '%s/site' % gluondir
makedirs(sitedir)
copy(siteconf, sitedir)
copy(sitemk, sitedir)
copytree(i18ndir, '%s/i18n' % sitedir)

# Prepare
chdir(gluondir)
print('Updating other repositories... ', end=''); stdout.flush()
with open('%s/update.log' % logdir, 'w') as log:
    check_call('make update V=s', stdout=log, stderr=log, shell=True)
print('OK'); stdout.flush()

# Choose targets to build
if 'GLUON_TARGETS' in environ:
    targets = environ['GLUON_TARGETS'].split()
else:
    targets = [f for f in listdir('targets') if isdir('targets/%s' % f)]

# Build
for target in targets:
    print('Building for target %s... ' % target, end=''); stdout.flush()
    arch, variant = target.split('-')
    target_start = datetime.now()

    with open('%s/%s_stdout.log' % (logdir, target), 'w') as logout, open('%s/%s_stderr.log' % (logdir, target), 'w') as logerr:
        rc = call('make -j %s GLUON_BRANCH=%s BROKEN=%s GLUON_TARGET=%s V=s' % (cpu_count()+1, branch, broken, target), stdout=logout, stderr=logerr, shell=True)
    duration = format_duration(datetime.now() - target_start)
    if rc == 0:
        print('OK in', duration)

        # Create manifest
        print('Creating manifest... ', end=''); stdout.flush()
        with open('%s/%s_manifest.log' % (logdir, target), 'w') as log:
            rc = call('make manifest GLUON_BRANCH=%s BROKEN=%s GLUON_TARGET=%s V=s' % (branch, broken, target), stdout=log, stderr=log, shell=True)
        if rc == 0:
            rename('output/images/sysupgrade/%s.manifest' % branch, 'output/images/sysupgrade/%s.%s.manifest' % (target, branch))
            print('OK')
        else:
            print('FAILED')
        stdout.flush()

        # Move images to output
        for f in listdir('output/images/factory'):
            rename('output/images/factory/%s' % f, '%s/%s' % (factorydir, f))
        for f in listdir('output/images/sysupgrade'):
            rename('output/images/sysupgrade/%s' % f, '%s/%s' % (sysupdir, f))

        # Move modules to output
        try:
            makedirs('%s/%s' % (modulesdir, arch))
        except FileExistsError:
            pass
        variantdir = '%s/%s/%s' % (modulesdir, arch, variant)
        rename('output/modules/gluon-%s-%s/%s/%s' % (site, release, arch, variant), variantdir)

        # Checksum modules
        print('Creating SHA512 sums for modules... ', end=''); stdout.flush()
        chdir(variantdir)
        check_call('sha512sum * > sha512sum.txt', shell=True)
        chdir(gluondir)
        print('OK')
    else:
        print('FAILED after', duration)

    # Clean up
    print('Cleaning up...', end=''); stdout.flush()
    with open('%s/%s_cleanup.log' % (logdir, target), 'w') as log:
        check_call('make dirclean V=s', stdout=log, stderr=log, shell=True)
    print('OK'); stdout.flush()

print('Creating SHA512 sums for images... ', end=''); stdout.flush()
for d in (factorydir, sysupdir):
    chdir(d)
    check_call('sha512sum * > sha512sum.txt', shell=True)
print('OK')

print('''
BUILD FINISHED in %s

You can copy the resulting images from the container using:
docker cp %s:/usr/src/build/output <destination>
'''% (format_duration(datetime.now() - start), environ['HOSTNAME']))

