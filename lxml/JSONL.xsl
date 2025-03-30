<?xml version='1.0' encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<!--
   ===================================================================
GNU General Public License 2, or (at your option) any later version.
   ===================================================================
-->
<xsl:output method='text'/>

<xsl:variable name="surname-count" select="count(query/surnames/surname)"/>
<xsl:variable name="place-count" select="count(query/places/place)"/>

<xsl:template match="/">

<xsl:for-each select="query/surnames/surname">
   <xsl:text>{"surname":"</xsl:text>
      <xsl:value-of select="."/>
   <xsl:text>"}&#xa;</xsl:text>
</xsl:for-each>
<xsl:for-each select="query/places/place">
   <xsl:text>{"place":"</xsl:text>
      <xsl:value-of select="."/>
      <xsl:text>","lang":"</xsl:text>
   <xsl:text>"}&#xa;</xsl:text>
</xsl:for-each>
<xsl:for-each select="query/sources/source">
   <xsl:text>{"source":"</xsl:text>
      <xsl:value-of select="."/>
   <xsl:text>"}&#xa;</xsl:text>
</xsl:for-each>
</xsl:template>
</xsl:stylesheet>
