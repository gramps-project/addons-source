# My cookbook for gramplet production
## 1. Prerequsites
Working on a linux mint version 21.3

Installed repo version of:

1. Visual Studio Code - for python coding
2. gvim -for text files 
3. pylint - for checking my python code
4. black - for refactoring my code to the coding guidelines
5. xgettext - for creating .pot template file for internationalisation 
6. msmerge for updating the language file, when the template changed
7. remarkable - for creating Mark Down files
8. git - for version tracking

## 2. Startup
During my genealogical research, I missed seeing what was going on in the society when my ancestors lived.

Other applications have a build in timeline, and I thought gramps needed this.

**Needs** 

I defined my needs as a

* gramplet on person and relationship view
* Should show important historical event with the year the happened
* should be easily modifiable, and have a link to the event on internet
* should have different timeline, since my ancestors cam from both Sweden and Denmark, and some relatives to them emigrated to the US.
* The events should be colorized so you clearly could see what happened during the persons lifetime 
* I use the censuses in Denmark often, but cannot remember the years, so I included these in my CSV file: `da_DK_data_v1_0.txt` these entries should be able to be hidden, by applying a filter.

**Preparation**

Since I didn't't know anything about python and GTK+, I started by creating a standalone app, which fulfilled my needs.
I normally code in FPC/Lazarus, which comes with its own IDE, and use VI and/or gVim for anything else, but I soon found out that a new IDE was needed, after a little research I decided for Visual Studio Code, which is OK, but not nearly as good as Lazarus - or - perhaps it is just what I am used to.

I decided for a CSV file with ";" semicolon as a delimiter. It is fast to edit and requires no knowledge of the creator. 4 fields start year, end year, event and link to event

I am not good at reading documentation, and creating code from that, so I looked around on the net, and found a few examples, which reminded me of the task I was working on.

Copied, stole and experimented, and finally I had something working: Time to get on with the real job.

Created a grampsdev directory, and cloned three projects from the gramps git hub:
gramps
addons
addons-source

**The work**

Went to grampsdev/addons-source/HistContext directory (not really it was changed from another name) 
Created my app/HistContext outside the grampsdev tree, and created my own git repo for the gramplet
Created the .gramps/gramps52/plugins/Histcontext directory for testing (Not recommended if you update anything in the database)

Found out that I had a lot of copying to do for testing, so I ended up making symbolic links from my developments files to the plugin directory.

Started by copying the "Hello world" gramplet from the wiki, copied the files to my test directory and - hooray - it worked.
Renamed the files to HistContext.gpr.py and HistContext.py

Then I changed the relevant fields in the HistContect.gpr.py, and started looking for gramplets which loaded a person, and used GTK3 graphics.

I copied, stole and experimented, and finally I had something working. But I had several user definable options, and I had created a class which could create, read and write ini files, and store them in the location proposed by
[XDG base directory recommendation](https://specifications.freedesktop.org/basedir-spec/latest/) https://specifications.freedesktop.org/basedir-spec/latest/

Luckily I found that you could define and access settings from the settings dialog of the view. So I just had to rewrite the code, again searching in the plugins for a working example, and copied it, and after modification it worked.

So now for cooperation with gramps users an developers. I use the [gramps dscource group for that](https://gramps.discourse.group/) for that, and it has been a real pleasure for the help, and feedback I have got from that group.

I soon found out that people use the gramplet in other ways than I thought of, and several errors was detected, as well as some very bright ideas for enhancement. I will just summarize:

1. use black to refactor your code, for ensuring that it works with rest of gramps.
2. The ini file should be persistent and reside in the plugin directory - use register
3. The CSV files should be able to have different date formats.
4. Possibility to hide events outside a persons life span.
5. don't hard code anything a user might want to change. In my case: colors of foreground and background, which text file(s) to use, only use years for events.
6. Remember that other may want to read and understand your code, so better comment, and use meaningful variable names.
7. Don't be afraid to ask for help
8. Don't be shy of your coding style and lack of knowledge - people will not laugh of you. worst thing tha may happen, is you get some goog advice 

OK back to the project:
  	
1. Make a git branch of addons-source directory, and clone that branch to the copy you have en the garmpsdev director.
2. Copy your gramplet directory in to that and do a commit and push.
3. Wait and see if someone explodes.

If you think you is done with the feed back, make a pull request

## some tips
I am not good with the debugger, so I use local_log.info("var = %s") for the debugging.

Set log level to info, and start gramps from command line to see the message.

Remember to remove your unneeded info, and to set the log level to warning.

When documenting using screen shots, you should move the gramplet to a "floating" position

Creating some documentation and help text, use Makk Down format in your gramplet directory, it will not be distributed, but is a good help for creating the wiki help, when you are done, and the beta testers will be able to see it.

Commit often, you will sooner or later introduce unwanted errors or side effects.

 


