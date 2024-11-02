### Histtory Context gramplet

Gramplet to display historical events with the year they happened, and optionally the year  they ended.
A double-click on a row will open your browser at the provided Link

The gramplet works on the person and the relations view.
The data for the gramplet comes from a CSV file, which can be edited with a normal editor.

The Format is:

`from;to;event;link to event`

example:

1789;1797;George Washington;https://en.wikipedia.org/wiki/George\_Washington

The file name is `<locale>_data_v1_0.txt `e.g. `da_DK_data_v1_0.txt` for Denmark
Currently only four files are provided, `da_DK_data_v1_0.txt` and `en_US_data_v1_0.txt` which simply is a list of American presidents.
The third is `deafult_data_v1_0.txt`which will be used, if there isn't any data file for your language.
The fourth file is `custom_v1_0.txt`which can be used for adding your own data, which will be merged into the view.

You can select the data file form the options in the view

In the options you can also elect whether you want see all historical data, or only those in the focus persons lifetime 

I have added all the danish census'es to the Danish data file. To avoid looking at this you can go into the settings for the person list, and make a filter. If you check the "use filter" checkbox, the historical list will not display the events starting with the text you have added. In my case the text is "Folketælling"


