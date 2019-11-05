#!/usr/bin/python3
import csv
import fileinput

loaded_packages = {}
for line in fileinput.input():
    line = line.strip().replace(',','').replace('(','').replace(')','')
    name = line.split('wants:')[0].strip().split(' ')[-1]
    deps = set(filter(lambda x: x!='',line.split('wants:')[1].strip().split(' ')))
    loaded_packages[name] = {'orig':deps,'done':deps}

packages = {}
while len(loaded_packages) != 0:
    for name,deps in loaded_packages.items():
        if len(deps['done']) != 0:
            continue
        
        del loaded_packages[name]
        packages[name] = deps['orig']
        for name2, deps2 in loaded_packages.items():
            if name in deps2['done']:
                loaded_packages[name2]['orig'] = loaded_packages[name2]['orig'].union(deps['orig'])
                loaded_packages[name2]['done'].discard(name)
        
        break
    
for name,deps in packages.items():
    deps_line = ' '.join(deps)
    dep_count = len(list(filter(lambda x: name in x[1], packages.items())))
    
    print('{},{},{}'.format(dep_count,name,deps_line,deps_line))
