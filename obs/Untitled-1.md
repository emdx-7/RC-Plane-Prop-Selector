Looks good for demo:

make a response for me to feed to next instance to save context and not water down compaction. 

TODO Left:
1. Sliders for:
a) 3d plot x and y axises
b) 2 speed in put slices (add a rebuild button for the 2d plots, don't dynamcally update to slider) 

2. Add more data to the propeller summary at the bottom of the comparison card
Should be formatted as name in bold as is, then have table with clear fields, not misc stuff. add prop geometry, planform, etc. 

3. add a toggle to plot/overlay emperical data from UIUC bank (don't implement, just add the UI item - feature later)

The actual Implementation:
1. need parser to run through UIUC data and APC data and make a folder with all the processed prop data.
2. rebuild demo plotter with added functions, and prop selection feature
3. figure out empirical data integration and toggle (one detail is I want to interpolate linearly for 2D slices between data points, but NEVER extrapolate

4. Separate filtering/sorting/candidate tool that enables showing a singular 2D plot (can configure which plot) + summary per foil

lets make a plan