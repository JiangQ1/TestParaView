# This plugin demonstrates how to add a new representation to ParaView that
# employs hardware shaders. The shaders are employed by the
# vtkVisibleLinesPainter which is initialized by the
# vtkGeometryRepresentationWithHiddenLinesRemoval.
# This plugin add a new representation-type
# "Visible Wireframe" when showing polydata in a 3D view.

# Note that this plugin does not work in parallel since it relies on composited
# Z-buffer and currently there's not support to obtain a composited Z-buffer
# during the rendering stage.

cmake_minimum_required(VERSION 2.8.8 FATAL_ERROR)

if (NOT ParaView_BINARY_DIR)
  find_package(ParaView REQUIRED)
  include(${PARAVIEW_USE_FILE})
endif()

include(ParaViewPlugins)


# Compile-in all GLSL files are strings.
# const char* with the names same as that of the file then become available for
# use.
encode_files_as_strings(ENCODED_STRING_FILES
  vtkPVLightingHelper_s.glsl
  vtkPVColorMaterialHelper_vs.glsl
  vtkVisibleLinesPainter_fs.glsl
  vtkVisibleLinesPainter_vs.glsl
  )

add_paraview_plugin(
  HiddenLinesRemoval "1.0"
  SERVER_MANAGER_XML
          HiddenLinesRemovalPlugin.xml

  SERVER_MANAGER_SOURCES
          vtkGeometryRepresentationWithHiddenLinesRemoval.cxx

  SOURCES vtkPVColorMaterialHelper.cxx
          vtkPVLightingHelper.cxx
          vtkVisibleLinesPainter.cxx
          ${ENCODED_STRING_FILES}
)
