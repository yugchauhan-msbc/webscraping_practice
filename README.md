

From: Sushant Singh <s.singh@remoratech.io> 
Sent: Tuesday, June 16, 2026 3:30 PM
To: Deep Dave <deep.dave@msbcgroup.com>
Subject: Fw: Pizzint.Watch Scrape - 1.8.26

Hi Deep

Please see below mail. Read through it, there are two mails below for one scrape. I will send others.

Regards
Sushant
 
External Email: This email originated from outside of our organization. Please exercise caution and not click links or open attachments unless you recognize the sender and know the content is safe..
Seems like theres a new section on the website – ‘Nothing Ever Happens Index’. Can team take a look at adding this section to the scrape as well?
https://www.pizzint.watch/nothingeverhappens
 
Sample Schema:
DataDate	Time	Section	DataName	Status	Metric	Value
1/8/2026	7:17pm	Nothing Ever Happens Index	Khamenei out as Supreme Leader of Iran by January 31st?	Nothing Ever Happens	Value	0.18
1/8/2026	7:17pm	Nothing Ever Happens Index	China x Taiwan military clash before 2027	Nothing Ever Happens	Value	0.18
 
 
In order to categorize status, can use their ranges of 0-29 is Nothing Ever Happens, 30-64 is Something Might Happen, etc.
 
Please let us know if you have any questions.
 
Thanks,
Elliot
 
 
From: Sushant Singh <s.singh@remoratech.io>
Sent: Thursday, January 8, 2026 11:27 PM
To: Elliot Tan <ETan@juntocap.com>; Pratik_Patil <p.patil@remoratech.io>
Cc: QROps <QROps@juntocap.com>
Subject: Re: Pizzint.Watch Scrape - 1.8.26
 
Hi Elliot, 
 
We will review and work on it.
 
Regards
Sushant
________________________________________
From: Elliot Tan <ETan@juntocap.com>
Sent: Friday, January 9, 2026 5:59 AM
To: Sushant Singh <s.singh@remoratech.io>; Pratik Patil <p.patil@remoratech.io>
Cc: QROps <QROps@juntocap.com>
Subject: Pizzint.Watch Scrape - 1.8.26
 
External Email: This email originated from outside of our organization. Please exercise caution and not click links or open attachments unless you recognize the sender and know the content is safe..
Hi team,
 
We would like to begin scraping this website: https://www.pizzint.watch/ (please let us know if team finds an API, which could be interesting for other use cases).
 
There are two sections to scrape for now – the Pizza section, the Gay Bar section, and the PolyPulse Bilateral Threat Monitor.
 
Pizza:
We would like to scrape this section’s blue bars and the red bar is the _LIVE value. Example is in Sample Schema below. The status would be the text in the box, such as Quiet or Nominal.
 
 
Gay Bar Report:
Same thing as the pizza section
 
 
Polypulse:
We would like to scrape the value of each of these combinations (e.g. USA/RUS) for the value as well as the text in the box (e.g. Elevated, Critical).
 
 
Sample Schema:
DataDate	Time	Section	DataName	Status	Metric	Value
1/8/2026	7:17pm	Pizza	Dominos Pizza_6pm	Quiet	Value	0.45
1/8/2026	7:17pm	Pizza	Dominos Pizza_6pm_LIVE	Quiet	Value	0.8
1/8/2026	7:17pm	PolyPulse - Bilateral Threat Monitor	CHN /TWN	Elevated	Value	3.07
1/8/2026	7:17pm	PolyPulse - Bilateral Threat Monitor	USA / IRN	Elevated	Value	1.2
 
•	Table Name can be PIZZINT_WATCH
•	Primary Keys are DataDate, Time, Section, DataName, Metric
•	DataDate is date and Time is time (not string), everything else can be string, value can be float
•	To start, can we please scrape every 30 minutes assuming this is possible.
 
Please let us know if you have any questions, thanks.
 
Thanks,
Elliot
 
The information contained in this transmission may contain privileged and confidential information.  It is intended only for the use of the person(s) named above.  If you are not the intended recipient, you are hereby notified that any review, dissemination, distribution or duplication of this communication is strictly prohibited.  This communication is for information purposes only and should not be regarded as an offer to sell or as a solicitation of an offer to buy any financial product, an official confirmation of any transaction, or as an official statement of Junto Capital Management LP.  If you are not the intended recipient, please contact the sender by replying to this e-mail and destroy all copies of this e-mail (and any attachment(s)) from your system.
This email and any attachments are intended solely for the addressee. The information contained herein and attached are confidential and the property of MSBC. If you are not the intended addressee or recipient, please be advised that viewing this message and any attachment/s, as well coping, forwarding, printing and disseminating any information related to the email and attachment/s are prohibited, and that you should not take any action based on that content of this e-mail and/or its attachment/s. If you received this message or any attachment in error, please notify the sender immediately, delete it permanently from your system & any synced devices or application. Internet communications are not guaranteed to be secure or without viruses. MSBC does not accept responsibility for any loss arising from unauthorised access to, or interference with, any Internet communications by any third party, or from the transmission of any viruses. Replies to this email may be monitored by MSBC for operational or business reasons. Any opinion or other information in this email or its attachments that does not relate to the business of the MSBC is personal to the sender and is not given or endorsed by MSBC.











From: Pratik Patil <p.patil@remoratech.io> 
Sent: Tuesday, June 16, 2026 2:48 PM
To: Deep Dave <deep.dave@msbcgroup.com>
Cc: Sushant Singh <s.singh@remoratech.io>
Subject: FW: Fixing Prediction Market scrape + small addition

Main site :- https://dune.com/datadashboards/prediction-markets

From: Preston Smith <PSmith@juntocap.com> 
Sent: 05 January 2026 19:06
To: Sushant Singh <s.singh@remoratech.io>; Pratik Patil <p.patil@remoratech.io>
Cc: QROps <QROps@juntocap.com>
Subject: Fixing Prediction Market scrape + small addition

External Email: This email originated from outside of our organization. Please exercise caution and not click links or open attachments unless you recognize the sender and know the content is safe..
Hello,

Can team please look into this potential error on the Prediction Market Dune data scrape? The Dune website has the following notional volume chart:

 

However, our monthly chart based on this data looks incorrect (look at 12/2025 in particular): 
  

While you’re looking into this, can you also add Opinion (Opinion Labs) as another platform in the scrape. Please scrape all the same variables for Opinion as you did for Polymarket.

Let me know if you have any questions.

Thanks!
Preston


Preston Smith
Junto Capital Management LP
550 Madison Avenue, 33rd Floor
New York, NY 10022
(212) 409-1979
psmith@juntocap.com

The information contained in this transmission may contain privileged and confidential information.  It is intended only for the use of the person(s) named above.  If you are not the intended recipient, you are hereby notified that any review, dissemination, distribution or duplication of this communication is strictly prohibited.  This communication is for information purposes only and should not be regarded as an offer to sell or as a solicitation of an offer to buy any financial product, an official confirmation of any transaction, or as an official statement of Junto Capital Management LP.  If you are not the intended recipient, please contact the sender by replying to this e-mail and destroy all copies of this e-mail (and any attachment(s)) from your system.
