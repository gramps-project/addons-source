<?xml version='1.0' encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<!--
   ===================================================================
GNU General Public License 2, or (at your option) any later version.
   ===================================================================
-->
<xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>

<xsl:variable name="surname-count" select="count(query/surnames/surname)"/>
<xsl:variable name="place-count" select="count(query/places/place)"/>

<xsl:template match="/">

<html>
    <xsl:attribute name="lang">
       <xsl:value-of select="query/@lang"/>
    </xsl:attribute>
    <head>
        <link rel="stylesheet" type="text/css" href="lxml.css"/>
        <script type ="text/javascript">function next()
             {
             alert("Submit cancelled, only for testing!");
             return false
             }
        </script>
    </head>
    <body>
        <h1><xsl:value-of select="query/@title"/></h1>
        <h2><xsl:value-of select="query/surnames/@title"/><xsl:text> : </xsl:text>
        <xsl:value-of select="$surname-count"/></h2>
        <form xmlns="http://www.w3.org/1999/xhtml" action="." method="get" onsubmit="next()">
        <select name="slist">
           <xsl:for-each select="query/surnames/surname">
              <option>
                 <xsl:attribute name="value">
                    <xsl:value-of select="."/>
                 </xsl:attribute>
                 <xsl:value-of select="."/>
              </option>
           </xsl:for-each>
        </select>
        <div align="right">
        <input type="submit">
           <xsl:attribute name="value">
              <xsl:value-of select="query/@title"/>
           </xsl:attribute>
        </input>
        </div>
        </form>
        <h2><xsl:value-of select="query/places/@title"/><xsl:text> : </xsl:text>
        <xsl:value-of select="$place-count"/></h2>
        <form xmlns="http://www.w3.org/1999/xhtml" action="." method="get" onsubmit="next()">
           <xsl:attribute name="xml:lang">
              <xsl:value-of select="query/@lang"/>
           </xsl:attribute>
           <div>
              <label for="/database/places/placeobj[1]/ptitle" class="element">
              <xsl:value-of select="query/clist/@ptitle"/></label><xsl:text> : </xsl:text>
              <select name="plist">
                 <option>
                    <xsl:attribute name="value">
                          <xsl:value-of select="None"/>
                       </xsl:attribute>
                    <xsl:text></xsl:text>
                 </option>
                 <xsl:for-each select="query/places/place">
                    <option>
                       <xsl:attribute name="value">
                          <xsl:value-of select="."/>
                       </xsl:attribute>
                       <xsl:value-of select="."/>
                    </option>
                 </xsl:for-each>
              </select>
           </div>
           <div>
              <label for="/database/places/placeobj[1]/location[1]/@city" class="attribute">
              <xsl:value-of select="query/clist/@city"/></label><xsl:text> : </xsl:text>
           </div>
           <div>
              <label for="/database/places/placeobj[1]/location[1]/@county" class="attribute">
              <xsl:value-of select="query/clist/@county"/></label><xsl:text> : </xsl:text>
           </div>
           <div>
              <label for="/database/places/placeobj[1]/location[1]/@state" class="attribute">
              <xsl:value-of select="query/clist/@state"/></label><xsl:text> : </xsl:text>
           </div>
           <div>
              <label for="/database/places/placeobj[1]/location[1]/@country" class="attribute">
              <xsl:value-of select="query/clist/@country"/></label><xsl:text> : </xsl:text>
              <select name="clist">
                 <xsl:for-each select="query/clist/country">
                    <option>
                       <xsl:attribute name="value">
                          <xsl:number value="position()" format="1"/>
                       </xsl:attribute>
                       <xsl:value-of select="."/>
                    </option>
                 </xsl:for-each>
              </select>
           </div>
           <div align="right"> 
           <input type="submit">
              <xsl:attribute name="value">
                 <xsl:value-of select="query/@title"/>
              </xsl:attribute>
           </input>
           </div>
        </form>
        <h2><xsl:value-of select="query/sources/@title"/><xsl:text> : </xsl:text></h2>
           <xsl:for-each select="query/sources/source">
              <p><xsl:number value="position()" format="1"/><xsl:text> : </xsl:text>
              <xsl:value-of select="."/></p>
           </xsl:for-each>
        <div align="right"><xsl:value-of select="query/@footer"/>-<xsl:value-of select="query/log/@version"/></div>
        <div align="right">(<i><xsl:value-of select="query/log/@date"/></i>)</div>
        <div align="right">(<i><xsl:value-of select="query/@first"/></i>-<i><xsl:value-of select="query/@last"/></i>)</div>
        <div align="left"><b><xsl:value-of select="query/@date"/></b></div>
        <div align="left"><b><xsl:value-of select="query/@lang"/></b></div>
    </body>
</html>

</xsl:template>

</xsl:stylesheet>
