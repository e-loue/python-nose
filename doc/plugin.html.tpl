<html>
  <head>
    <title>nose: %(title)s</title>
    <link rel="stylesheet" href="site.css" type="text/css"></link>
  </head>
  <body>
    
    <div id="menu">
      <p>This document covers nose version <b>%(version)s</b></p>
      <p>Last update: <b>%(date)s</b></p>
      %(menu)s
    </div>
    
    <div id="main">
      <h1>nose: %(title)s</h1>
      
      %(body)s

      <h2>Plugin Methods Implemented</h2>

      <p>This plugin implements the following plugin interface methods:</p>
      
      <ul>%(hooks)s</ul>


      <h2>Commandline Options</h2>

      <p>This plugin adds the following commandline options:</p>

      <pre>%(options)s</pre>

      <h2>Source</h2>

      %(source)s

    </div>
    <script src="http://www.google-analytics.com/urchin.js" 
	    type="text/javascript">
    </script>
    <script type="text/javascript">
      _uacct = "UA-2236166-1";
      urchinTracker();
    </script>
  </body>
</html>
  
