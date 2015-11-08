import StringIO


def write_gml(graph):
    gml = StringIO.StringIO()
    gml.write('graph\n[\n')
    gml.write('\tdirected 1\n')

    areGroupNodes = []
    for node in graph['node']:
        if 'parent' in node['data']:
            areGroupNodes.append(node['data']['parent'])
    for node in graph['node']:
        gml.write('node [\n')
        if 'parent' in node['data']:
            if node['data']['id'] in areGroupNodes:
                gml.write('\tid {0} label "{1}" isGroup 1 gid {2}  graphics [x {3} y {4} type "roundrectangle" fill "#FFFFFF" outline "#000000"]\
LabelGraphics [ text "{1}" anchor "t" fontStyle "bold"  ]'.format(node['data']['id'], node['data']['label'], node['data']['parent'],  node['position']['x'], node['position']['y']))
            else:
                gml.write('\tid {0} label "{1}" gid {2}  graphics [x {3} y {4} type "roundrectangle" fill "#FFFFFF" outline "#000000"]\
LabelGraphics [ text "{1}" anchor "t" fontStyle "bold"  ]'.format(node['data']['id'], node['data']['label'], node['data']['parent'],  node['position']['x'], node['position']['y']))
        else:
            gml.write('\tid {0} label "{1}" isGroup 1  graphics [x {2} y {3} type "roundrectangle" fill "#D2D2D2" outline "#000000"]\
LabelGraphics [ text "{1}" anchor "t" fontStyle "bold"  ]'.format(node['data']['id'], node['data']['label'], node['position']['x'], node['position']['y']))

        gml.write('\n]\n')

    for edge in graph['edge']:
        print edge
        gml.write('edge [ source {0} target {1}  graphics [ fill "#000000"  ] ]\n'.format(edge[0], edge[1]))

    gml.write(']\n')
    return gml.getvalue()
