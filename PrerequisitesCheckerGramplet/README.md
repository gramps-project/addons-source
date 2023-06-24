# PrerequisitesCheckerGramplet
light revision of Sam Manzi's 0.8.40 Prerequisite Checker

## The text reformatting includes: 
 - swapping in leading spaces & bullets for asterisks. 
 - italicizing descriptive text 
 - composing backup text and correcting menu labels  
 - making the Required-Recommended-optional section labels more consistent in tense 

## Updated Help URLs

Changed & tested the Help URLs to the new standard "Addon:" prefix and added a "in document" scrolling target. (Including the help_url in this Gramps Plugin's Registration file.)

##  A few issues.

Not critical - if the gramplet is added to a sidebar and Gramps is closed with preferences set to rember last view, then the Gramplet will have 3 COPIES of the report.

There are new developer tools. Does it need to check for:
 - Weblate
 - PyCharm
 - Glade

There are a bunch of TBDs when run the report 


The guys with the metadata viewer need a new library and they are unsure how to test.
See https://gramps.discourse.group/t/installing-prerequisites-for-a-windows-aio-bundle/2867/1
