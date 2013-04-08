r"""web_helper is a module that provides access to functions that helps to build
new protocols and process ParaView data structure into web friendly ones.
"""

import types
import sys
import os

# import paraview modules.
from paraview import simple, servermanager
from paraview.servermanager import ProxyProperty

# =============================================================================
# Pipeline management
# =============================================================================

class Pipeline:
    """
    Define a data structure that represent a pipeline as a tree.
    This provide also methods to get the data structure for the web environment
    """

    # --------------------------------------------------------------------------

    def __init__(self, name):
        self.root_node = { 'name': name, 'icon': 'server', 'children': [] }
        self.parent_ids = { '0':'0' }
        self.children_ids = { '0':[] }

    # --------------------------------------------------------------------------

    def clear(self):
        """
        Clear the pipeline tree.
        """
        self.root_node['children'] = []
        self.parent_ids = { '0':'0' }
        self.children_ids = { '0':[] }

    # --------------------------------------------------------------------------

    def addNode(self, parent_id, node_id):
        """
        Add node into the pipeline tree.
        """
        pid = str(parent_id)
        nid = str(node_id)

        # Add child
        if self.children_ids.has_key(pid):
            self.children_ids[pid].append(nid)
        else:
            self.children_ids[pid] = [nid]

        # Add parent
        self.parent_ids[nid] = pid

    # --------------------------------------------------------------------------

    def removeNode(self, id):
        """
        Remove a node from the pipeline tree.
        """
        nid = str(id)
        pid = self.parent_ids[nid]
        if pid:
            del self.parent_ids[nid]
            self.children_ids[pid].remove(nid)

    # --------------------------------------------------------------------------

    def getRootNode(self, lutManager = None):
        """
        Create a tree structure of the pipeline with the current proxy state.
        """
        self.root_node['children'] = []
        self.__fill_children(self.root_node, self.children_ids['0'], lutManager)
        return self.root_node

    # --------------------------------------------------------------------------

    def __fill_children(self, nodeToFill, childrenIds, lutManager = None):
        for id in childrenIds:
            node = getProxyAsPipelineNode(id, lutManager)
            nid = str(node['proxy_id'])

            if nodeToFill.has_key('children'):
                nodeToFill['children'].append(node)
            else:
                nodeToFill['children'] = [ node ]

            if self.children_ids.has_key(nid):
                self.__fill_children(node, self.children_ids[nid]);


# =============================================================================
# Lookup Table Management
# =============================================================================

class LookupTableManager:
    """
    Define a data structure that keep track of lookup tables and scalar bars
    """

    # --------------------------------------------------------------------------

    def __init__(self):
        self.luts = {}
        self.scalarbars = {}
        self.range = {}
        self.view = None

    # --------------------------------------------------------------------------

    def getLutId(self, name, number_of_components):
        return "%s_%d" % (name, number_of_components)

    # --------------------------------------------------------------------------

    def clear(self):
        """
        Clear the set of lookup table and scalar bar.
        """
        self.luts = {}
        self.scalarbars = {}

    # --------------------------------------------------------------------------

    def registerFieldData(self, data):
        if data:
            size = data.GetNumberOfArrays()
            for i in range(size):
                array = data.GetArray(i)
                name = array.Name
                nbComp = array.GetNumberOfComponents()
                dataRange = [0.0, 1.0]
                if nbComp == 3:
                    dataRange = array.GetRange(-1)
                else:
                    dataRange = array.GetRange(0)
                self.registerArray(name, nbComp, dataRange)

    # --------------------------------------------------------------------------

    def registerArray(self, name, number_of_components, range):
        key = self.getLutId(name, number_of_components)
        if self.range.has_key(key):
            self.range[key] = range;
            self.luts[key].RGBPoints = [range[0], 0, 0, 1, range[1], 1, 0, 0]
            self.luts[key].VectorMode = 'Magnitude'
            self.luts[key].ColorSpace = 'HSV'
        else:
            self.range[key] = range;
            # ... fixme ... Create default lut with proper range/title/color scheme
            self.luts[key] = simple.GetLookupTableForArray(name, number_of_components)

            # Setup default config
            self.luts[key].RGBPoints  = [range[0], 0, 0, 1, range[1], 1, 0, 0]
            self.luts[key].VectorMode = 'Magnitude'
            self.luts[key].ColorSpace = 'HSV'

            self.scalarbars[key] = simple.CreateScalarBar(LookupTable=self.luts[key])
            self.scalarbars[key].Title = name
            self.scalarbars[key].Visibility = 0
            self.scalarbars[key].Enabled = 0

            # Add scalar bar to the view
            if self.view:
                self.view.Representations.append(self.scalarbars[key])

    # --------------------------------------------------------------------------

    def getLookupTable(self, name, number_of_components):
        key = self.getLutId(name, number_of_components)
        return self.getLookupTableFromId(key)

    # --------------------------------------------------------------------------

    def getLookupTableFromId(self, id):
        if self.luts.has_key(id):
            return self.luts[id]
        return None

    # --------------------------------------------------------------------------

    def getScalarBar(self, name, number_of_components):
        key = self.getLutId(name, number_of_components)
        return self.getScalarBarFromId(key)


    # --------------------------------------------------------------------------

    def getScalarBarFromId(self, id):
        if self.scalarbars.has_key(id):
            return self.scalarbars[id]
        return None

    # --------------------------------------------------------------------------

    def isScalarBarVisible(self, id):
        if self.scalarbars.has_key(id):
            return self.scalarbars[id].Visibility
        return 0

    # --------------------------------------------------------------------------

    def enableScalarBar(self, name, number_of_components, show):
        key = self.getLutId(name, number_of_components)
        self.enableScalarBarFromId(key, show)

    # --------------------------------------------------------------------------

    def enableScalarBarFromId(self, id, show):
        if self.scalarbars.has_key(id):
            self.scalarbars[id].Visibility = show
            self.scalarbars[id].Enabled = show
            self.scalarbars[id].Repositionable = show
            self.scalarbars[id].Selectable = show

    # --------------------------------------------------------------------------

    def setView(self, view):
        if self.view:
            for value in self.scalarbars.values():
                try:
                    view.Representations.remove(value)
                except ValueError:
                    pass

        self.view = view
        for value in self.scalarbars.values():
            self.view.Representations.append(value)

    # --------------------------------------------------------------------------

    def getScalarbarVisibility(self):
        status = {};
        for key in self.scalarbars.keys():
            status[key] = {        \
                'lutId': key,       \
                'name': key[0:-2],   \
                'size': int(key[-1]), \
                'enabled': self.scalarbars[key].Visibility }
        return status

# =============================================================================
# Proxy management
# =============================================================================

def idToProxy(id):
    """
    Return the proxy that match the given proxy ID.
    """
    remoteObject = simple.servermanager.ActiveConnection.Session.GetRemoteObject(int(id))
    if remoteObject:
        return simple.servermanager._getPyProxy(remoteObject)
    return None

# --------------------------------------------------------------------------

def getProxyAsPipelineNode(id, lutManager = None):
    """
    Create a representation for that proxy so it can be used within a pipeline
    browser.
    """
    pxm = servermanager.ProxyManager()
    proxy = idToProxy(id)
    rep = simple.GetDisplayProperties(proxy)
    nbActiveComp = 1

    pointData = []
    searchArray = ('POINT_DATA' == rep.ColorAttributeType) and (len(rep.ColorArrayName) > 0)
    for array in proxy.GetPointDataInformation():
        nbComponents = array.GetNumberOfComponents()
        if searchArray and array.Name == rep.ColorArrayName:
            nbActiveComp = nbComponents
        rangeOn = (nbComponents == 3 if -1 else 0)
        info = {                                      \
        'lutId': array.Name + '_' + str(nbComponents), \
        'name': array.Name,                             \
        'size': nbComponents,                            \
        'range': array.GetRange(rangeOn) }
        pointData.append(info)

    cellData = []
    searchArray = ('CELL_DATA' == rep.ColorAttributeType) and (len(rep.ColorArrayName) > 0)
    for array in proxy.GetCellDataInformation():
        nbComponents = array.GetNumberOfComponents()
        if searchArray and array.Name == rep.ColorArrayName:
            nbActiveComp = nbComponents
        rangeOn = (nbComponents == 3 if -1 else 0)
        info = {                                      \
        'lutId': array.Name + '_' + str(nbComponents), \
        'name': array.Name,                             \
        'size': nbComponents,                            \
        'range': array.GetRange(rangeOn) }
        cellData.append(info)

    state = getProxyAsState(proxy.GetGlobalID())
    showScalarbar = 0
    if lutManager and (len(rep.ColorArrayName) > 0):
        showScalarbar = lutManager.isScalarBarVisible(rep.ColorArrayName + '_' + str(nbActiveComp))

    return { 'proxy_id'  : proxy.GetGlobalID(),                               \
             'name'      : pxm.GetProxyName("sources", proxy),                \
             'pointData' : pointData,                                         \
             'cellData'  : cellData,                                          \
             'activeData': rep.ColorAttributeType + ':' + rep.ColorArrayName, \
             'diffuseColor'  : str(rep.DiffuseColor),                         \
             'showScalarBar' : showScalarbar,                                 \
             'representation': rep.Representation,                            \
             'state'         : state,                                         \
             'children'      : [] }

# --------------------------------------------------------------------------

def getProxyAsState(id):
    """
    Return a json representation of the given proxy state.

    Example of the state of the Clip filter
      {
         proxy_id: 234,
         ClipType: {
            proxy_id: 235,
            Normal: [0,0,1],
            Origin: [0,0,0],
            InsideOut: 0
         }
      }
    """
    proxy_id = int(id)
    proxy = idToProxy(proxy_id)
    state = { 'proxy_id': proxy_id , 'type': 'proxy', 'domains': getProxyDomains(proxy_id)}
    properties = {}
    allowedTypes = [int, float, list, str]
    if proxy:
       for property in proxy.ListProperties():
          propertyName = proxy.GetProperty(property).Name
          if propertyName in ["Refresh"] or propertyName.__contains__("Info"):
             continue

          data = proxy.GetProperty(property).GetData()
          if type(data) in allowedTypes:
              properties[propertyName] = data
              continue

          print "Skip property: ", property, str(type(data)), str(type(data) in allowedTypes)
          print data

          if type(proxy.GetProperty(property)) == ProxyProperty:
              try:
                  subProxyId = proxy.GetProperty(property).GetData().GetGlobalID()
                  properties[propertyName] = getProxyAsState(subProxyId)
              except:
                  print "Error on", property, propertyName
                  print "Skip property: ", str(type(data))
                  print data
    state['properties'] = properties;
    return state

# --------------------------------------------------------------------------

def updateProxyProperties(proxy, properties):
   """
   Loop over the properties object and update the mapping properties
   to the given proxy.
   """
   allowedProperties = proxy.ListProperties()
   for key in properties:
      validKey = servermanager._make_name_valid(key)
      if validKey in allowedProperties:
         value = removeUnicode(properties[key])
         proxy.GetProperty(validKey).SetData(value)

# --------------------------------------------------------------------------

def removeUnicode(value):
    if type(value) == unicode:
        return str(value)
    if type(value) == list:
        result = []
        for v in value:
            result.append(removeUnicode(v))
        return result
    return value

# =============================================================================
# XML and Proxy Definition for GUI generation
# =============================================================================

def getProxyDomains(id):
   """
   Return a json based structured based on the proxy XML.
   """
   jsonDefinition = {}
   proxy = idToProxy(id)
   xmlElement = servermanager.ActiveConnection.Session.GetProxyDefinitionManager().GetCollapsedProxyDefinition(proxy.GetXMLGroup(), proxy.GetXMLName(), None)
   nbChildren = xmlElement.GetNumberOfNestedElements()
   for i in range(nbChildren):
       xmlChild = xmlElement.GetNestedElement(i)
       name = xmlChild.GetName()
       if name.__contains__('Property'):
           propName = xmlChild.GetAttribute('name')
           jsonDefinition[propName] = extractProperty(proxy, xmlChild)
           jsonDefinition[propName]['order'] = i

   # Look for proxy properties and their domain
   orderIndex = nbChildren
   for property in proxy.ListProperties():
       if property == 'Input':
           continue
       if type(proxy.GetProperty(property)) == ProxyProperty:
           try:
               subProxyId = proxy.GetProperty(property).GetData().GetGlobalID()
               subDomain = getProxyDomains(subProxyId)
               for key in subDomain:
                   jsonDefinition[key] = subDomain[key]
                   jsonDefinition[key]['order'] = orderIndex
                   orderIndex = orderIndex + 1
           except:
               print "(Def) Error on", property
               print "(Def) Skip property: ", str(type(data))

   return jsonDefinition

def extractProperty(proxy, xmlPropertyElement):
    propInfo = {}
    propInfo['name'] = xmlPropertyElement.GetAttribute('name')
    propInfo['label'] = xmlPropertyElement.GetAttribute('label')
    if xmlPropertyElement.GetAttribute('number_of_elements') != None:
        propInfo['size'] = xmlPropertyElement.GetAttribute('number_of_elements')
    propInfo['type'] = xmlPropertyElement.GetName()[:-14]
    propInfo['domains'] = []
    if xmlPropertyElement.GetAttribute('default_values') != None:
        propInfo['default_values'] = xmlPropertyElement.GetAttribute('default_values')
    nbChildren = xmlPropertyElement.GetNumberOfNestedElements()
    for i in range(nbChildren):
        xmlChild = xmlPropertyElement.GetNestedElement(i)
        name = xmlChild.GetName()
        if name.__contains__('Domain'):
            propInfo['domains'].append(extractDomain(proxy, propInfo['name'], xmlChild))
    return propInfo

def extractDomain(proxy, propertyName, xmlDomainElement):
    domainObj = {}
    name = xmlDomainElement.GetName()
    domainObj['type'] = name[:-6]

    # Handle Range
    if name.__contains__('RangeDomain'):
        if xmlDomainElement.GetAttribute('min') != None:
            domainObj['min'] = xmlDomainElement.GetAttribute('min')
        if xmlDomainElement.GetAttribute('max') != None:
            domainObj['max'] = xmlDomainElement.GetAttribute('max')

    # Handle Enum
    if name.__contains__('EnumerationDomain'):
        domainObj['enum'] = []
        nbChildren = xmlDomainElement.GetNumberOfNestedElements()
        for i in range(nbChildren):
            xmlChild = xmlDomainElement.GetNestedElement(i)
            if xmlChild.GetName() == "Entry":
                domainObj['enum'].append({'text': xmlChild.GetAttribute('text'), 'value': xmlChild.GetAttribute('value')})

    # Handle ArrayListDomain
    if name.__contains__('ArrayListDomain'):
        dataType = xmlDomainElement.GetAttribute('attribute_type')
        if dataType == 'Scalars':
            domainObj['nb_components'] = 1
        elif dataType == 'Vectors':
            domainObj['nb_components'] = 3
        else:
            domainObj['nb_components'] = -1

    # Handle ProxyListDomain
    if name.__contains__('ProxyListDomain'):
        domainObj['list'] = proxy.GetProperty(propertyName).Available

    return domainObj

# =============================================================================
# File Management
# =============================================================================

def listFiles(pathToList):
    """
    Create a tree structure of the given directory that will be understand by
    the pipelineBrowser widget.
    The provided path should not have a trailing '/'.

    return {
       children: [
           { name: 'fileName.vtk', path: '/full_path/to_file/fileName.vtk' },
           { name: 'directoryName', path: '/full_path/to_file/directoryName', children: [] }
       ]
    }
    """
    global fileList
    nodeTree = {}
    nodeTree[pathToList] = {'children': []}
    for path, directories, files in os.walk(pathToList):
        parent = nodeTree[path]
        for directory in directories:
            child = {'name': directory , 'path': (path + '/' + directory), 'children': []}
            nodeTree[path + '/' + directory] = child
            parent['children'].append(child)
        for filename in files:
            child = {'name': filename, 'path': (path + '/' + filename) }
            nodeTree[path + '/' + filename] = child
            parent['children'].append(child)
    fileList = nodeTree[pathToList]['children']
    return fileList