# Vision Station

A vision system for industrial fixed stations: a camera looks at a stopped object, and a job's tools judge the regions the user drew, answering PASS, FAIL or ERROR.

## Language

**Region**:
The area of the picture that one tool looks at, drawn by the user and placed relative to the frame or to a fixture.
_Avoid_: ROI (in interface text), window, zone

**Shape**:
The outline of a region when it is not a plain rectangle, made of one or more parts.
_Avoid_: Polygon, free-form area, custom region

**Part**:
One simple polygon of a shape. The region is the union of its parts.
_Avoid_: Piece, sub-region, island

**Bounding box**:
The smallest rectangle that holds a whole region. It is what the pipeline crops, and it is the whole region when there is no shape.
_Avoid_: Box, crop, rect (in docs and interface text)

**Mask**:
Which pixels of the cut region lie inside the shape. A tool that is given a mask counts only those pixels.
_Avoid_: Stencil, cut-out
