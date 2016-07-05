from collections import defaultdict
import json

def parseLog(rawLog):
    splitLog = rawLog.split('\n')
    categorizedLog = defaultdict(list)
    print splitLog
    for entry in splitLog:

        splitentry = entry.split(':')
        if len(splitentry) == 0:
            continue
        if 'ATO202' in splitentry[0]:
            options = []
            for splitoption in eval(splitentry[3]):
                optionstxt = """        ["{0}",[["{0}","{3}",[]]]],
        ["{2}",[["{2}","{1}",[]]]]""".format(splitoption[0], splitoption[0].lower(), splitoption[1], splitoption[1].lower())
                options.append([splitoption, optionstxt])
            categorizedLog['bonds'].append([', '.join(eval(splitentry[2])), options])
        elif 'SCT211' in splitentry[0]:
            options = set([])
            for splitoption in eval(splitentry[3]):
                optionstxt = '           "{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                options.add((str(splitoption), optionstxt))
            options = sorted(list(options))
            categorizedLog['stoich'].append((splitentry[2], options))
        elif 'ATO111' in splitentry[0]:
            options = set([])
            for splitoption in eval(splitentry[4]):
                if splitoption[0] != splitoption[1]:
                    optionstxt = """        ["{0}",[["{0}","{3}",[]]]],
            ["{2}",[["{2}","{1}",[]]]]""".format(splitoption[0], splitoption[0].lower(), splitoption[1], splitoption[1].lower())
                else:
                    optionstxt = '        ["{0}",[["{0}","{1}",[]]]]'.format(splitoption[0], splitoption[0].lower())
                options.add((str(splitoption), optionstxt))
            options = sorted(list(options))
            categorizedLog['biogrid'].append((splitentry[2], splitentry[6], options))
        elif 'SCT112' in splitentry[0] or 'SCT111' in splitentry[0]:
            options = set([])
            for splitoption in eval(splitentry[4]):
                optionstxt = '           "{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                options.add((str(splitoption), optionstxt))
            options = sorted(list(options))
            categorizedLog['conflict'].append((splitentry[2], splitentry[6], options))
        elif 'SCT113' in splitentry[0]:
            options = set([])
            for splitoption in eval(splitentry[4]):
                optionstxt = '           "{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                options.add((str(splitoption), optionstxt))
            options = sorted(list(options))
            categorizedLog['nolexicalconflict'].append((splitentry[2], splitentry[6], options))


    return categorizedLog

