from collections import defaultdict
import json

def parseLog(rawLog, rawReactions):
    """
    creates the information that will be used to build up radio buttons in atomizationResults.html
    based on the atomization log
    """
    splitLog = rawLog.split('\n')
    categorizedLog = defaultdict(list)
    helper = defaultdict(str)
    forceEquivalenceDict = {}
    cycleEquivalence = []
    for entry in splitLog:

        splitentry = entry.split(':')
        if len(splitentry) == 0:
            continue
        if 'ATO202' in splitentry[0]:
            options = []
            for splitoption in eval(splitentry[3]):
                optionstxt = """["{0}",[["{0}","{3}",[]]]],
["{2}",[["{2}","{1}",[]]]]""".format(splitoption[0], splitoption[0].lower(), splitoption[1], splitoption[1].lower())
                options.append([str(splitoption).translate(None, "'"), optionstxt])
            categorizedLog['bonds'].append([[x for x in eval(splitentry[2])], options])
        elif 'SCT211' in splitentry[0]:
            options = set([])
            for splitoption in eval(splitentry[3]):
                optionstxt = '"{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                options.add((str(splitoption).translate(None, "'"), optionstxt))
            options = sorted(list(options))
            categorizedLog['stoich'].append((str(splitentry[2]).translate(None, "'"), options))
        elif 'ATO111' in splitentry[0]:
            options = []
            i = -1
            for splitoption in eval(splitentry[4]):
                if splitoption[0] != splitoption[1]:
                    optionstxt = """["{0}",[["{0}","{3}",[]]]],
["{2}",[["{2}","{1}",[]]]]""".format(splitoption[0], splitoption[0].lower(), splitoption[1], splitoption[1].lower())
                else:
                    optionstxt = '["{0}",[["{0}","{1}",[]]]]'.format(splitoption[0], splitoption[0].lower())
                if (str(splitoption).translate(None, "'"), optionstxt) not in options:
                    options.append((str(splitoption).translate(None, "'"), optionstxt))
                    if str(splitoption) == str(splitentry[6]):
                        i = len(options) - 1

            # place the option choose by atomizer as the first radio button
            if(i > 0):
                options[i], options[0] = options[0], options[i]
            categorizedLog['biogrid'].append((str(splitentry[2]).translate(None, "'"), str(splitentry[6]).translate(None, "'"), options))

        elif 'SCT112' in splitentry[0] or 'SCT111' in splitentry[0]:
            options = []
            if 'SCT111' in splitentry[0]:
                optionstxt = '"{0}":{1}'.format(splitentry[2], json.dumps(eval(splitentry[6])[0]))
                options.append((str(eval(splitentry[6])[0]).translate(None,"'"), optionstxt))
            for splitoption in eval(splitentry[4]):
                optionstxt = '"{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                options.append((str(splitoption).translate(None, "'"), optionstxt))
            print options
            categorizedLog['conflict'].append((str(splitentry[2]).translate(None, "'"), str(splitentry[6]).translate(None, "'"), options))

        elif 'SCT113' in splitentry[0]:
            i = -1
            options = []
            for splitoption in eval(splitentry[4]):
                optionstxt = '"{0}":{1}'.format(splitentry[2], json.dumps(splitoption))
                if (str(splitoption).translate(None, "'"), optionstxt) not in options:
                    options.append((str(splitoption).translate(None, "'"), optionstxt))
                    if str(splitoption) == str(splitentry[6]):
                        i = len(options) - 1
            # place the option choose by atomizer as the first radio button            
            if(i > 0):
                options[i], options[0] = options[0], options[i]
            categorizedLog['nolexicalconflict'].append((str(splitentry[2]).translate(None, "'"), str(splitentry[6]).translate(None, "'"), options))

        elif 'SCT212' in splitentry[0]:
            options = set([])
            candidates = eval(splitentry[5])
            for splitoption in candidates:
                value = [x for x in candidates if x != splitoption]
                newChemical = '{0}{1}'.format(splitoption, splitentry[6])
                value.append(newChemical)
                optionstxt = '''"{2}":["{3}"],
"{0}":{1}'''.format(splitentry[3], json.dumps(value), newChemical, splitoption)
                options.add((str(splitoption).translate(None, "'"), optionstxt))
            options = sorted(list(options))
            categorizedLog['modstoich'].append((str(splitentry[3]).translate(None, "'"), str(splitentry[2]).translate(None, "'"), options))            
        elif 'LAE002' in splitentry[0]:
            if splitentry[3] not in forceEquivalenceDict:
                forceEquivalenceDict[splitentry[3].strip()] = set([])
            forceEquivalenceDict[splitentry[3].strip()].add(splitentry[3].strip())
            forceEquivalenceDict[splitentry[3].strip()].add(splitentry[4].strip())
            forceEquivalenceDict[splitentry[3].strip()].add(splitentry[5].strip())

        elif 'SCT221' in splitentry[0]:
            flag = False
            for x in cycleEquivalence:
                if splitentry[2].strip() in x or splitentry[3].strip() in x:
                    x.add(splitentry[2].strip())
                    x.add(splitentry[3].strip())
                    flag = True
                    break
            if not flag:
                cycleEquivalence.append(set([splitentry[2].strip(), splitentry[3].strip()]))
        elif 'SCT241' in splitentry[0]:
            overlapping = [splitentry[2], splitentry[3]]
            categorizedLog['samedef'].append([overlapping, eval(splitentry[5])])
    for entry in forceEquivalenceDict:
        entries = list(forceEquivalenceDict[entry])
        i = entries.index(entry)
        entries[i], entries[0] = entries[0], entries[i]
        categorizedLog['equivalences'].append((entries, json.dumps(entries)))
    for entry in cycleEquivalence:
        categorizedLog['cycles'].append((list(entry), json.dumps(list(entry))))
    return categorizedLog

