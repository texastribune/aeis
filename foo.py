# coding: utf-8

def targets():
    import glob
    for path in glob.glob('data/target/*.json.txt'):
        yield path
        
list(targets())
len(list(targets())
)
import os
def key(target):
    os.path.basename(target).replace('.json.txt', '')
    
key('data/target/foo.json.tx')
print key('data/target/foo.json.tx')
def key(target):
    basename = os.path.basename(target)
    return basename.replace('.json.txt', '')
key('data/target/foo.json.txt')
districts = (t for t in targets() if len(key(t)) == 6)
len(districts)
len(list(districts))
len(list(districts))
len(list(districts))
def districts():
    for target in targets:
        if len(key(target)) == 6):
            yield target
            
def districts():
    for target in targets:
        if len(key(target)) == 6:
            yield target
            
len(list(districts())
)
len(list(districts()))
len(list(districts()))
districts()
list(districts())
print list(districts())
def districts():
    for target in targets():
        if len(key(target)) == 6:
            yield target
            
print list(districts())
len(list(districts()))
len(list(districts()))
len(list(districts()))
def district_enrollment():
    for target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') == 'enrollment':
                print data
                
import json
print next(district_enrollment())
def district_enrollment():
    for target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') != 'enrollment':
                continue
   elif data.get('version') == 1994:
       continue
   elif data.get('measure') != 'count':
       continue
   yield data
   
def district_enrollment():
    for target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') != 'enrollment':
                continue
            elif data.get('version') == 1994:
                continue
            elif data.get('measure') != 'count':
                continue
            yield data
            
next(district_enrollment())
next(district_enrollment())
next(district_enrollment())
next(district_enrollment())
next(district_enrollment())
next(district_enrollment())
next(district_enrollment())
list(district_enrollment())
for data in district_enrollment(): print data
def districts():
    for target in targets():
        target_key = key(target)
        if len(target_key) == 6:
            yield target_key, target
            
def district_enrollment():
    for key, target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') != 'enrollment':
                continue
            elif data.get('version') == 1994:
                continue
            elif data.get('measure') != 'count':
                continue
            yield key, data
            
for key, data in district_enrollment(): print key, data
c
for key, data in district_enrollment(): print key, data
for key, data in district_enrollment(): print key, data
def district_enrollment():
    for key, target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') != 'enrollment':
                continue
            elif data.get('version') == 1994:
                continue
            elif data.get('measure') != 'count':
                continue
            yield key, data
            
for key, data in district_enrollment(): print key, data
def get_key(target):
    basename = os.path.basename(target)
    return basename.replace('.json.txt', '')
def districts():
    for target in targets():
        target_key = get_key(target)
        if len(target_key) == 6:
            yield target_key, target
            
def district_enrollment():
    for key, target in districts():
        for line in open(target):
            data = json.loads(line)
            if data.get('field') != 'enrollment':
                continue
            elif data.get('version') == 1994:
                continue
            elif data.get('measure') != 'count':
                continue
            yield key, data
            
for key, data in district_enrollment(): print key, data
for key, data in district_enrollment(): print key, data
get_ipython().magic(u'save foo')
get_ipython().magic(u'save foo *')
