

From: Sushant Singh <s.singh@remoratech.io> 
Sent: 05 January 2026 22:38
To: Lalit Suthar <Lalit.Suthar@msbcgroup.com>; Smeet Thadeshwar <smeet.thadeshwar@msbcgroup.com>; Shreyash Sonar <s.sonar@remoratech.io>
Subject: Fw: Dupont Registry Scrape - 1.5.26


Smeet work on this scrape. After this do the cme ingestion.

________________________________________
From: Elliot Tan <ETan@juntocap.com>
Sent: Monday, January 5, 2026 9:07:35 PM
To: Sushant Singh <s.singh@remoratech.io>; Pratik Patil <p.patil@remoratech.io>
Cc: QROps <QROps@juntocap.com>
Subject: Dupont Registry Scrape - 1.5.26 
 
External Email: This email originated from outside of our organization. Please exercise caution and not click links or open attachments unless you recognize the sender and know the content is safe..
Hi team,
 
Can you please scope out the below scrape and let us know if follows compliance.
 
We would like to scrape used Ferrari car information from Dupont registry. When searching, need to specify Condition and Listings, so there are two links:
1.	Listing = Dealer, Condition = Used: https://www.dupontregistry.com/autos/results/ferrari/all/dealer/filter:listingtypes=used
2.	Listing = Private Seller, Condition = Used: https://www.dupontregistry.com/autos/results/ferrari/all/private/filter:listingtypes=used
 
There are two sources of information – items from the front page and items from the page when clicking in. Condition and Listing comes from the search parameters listed above, and then Price + Vehicle are included on the front page.
 
Front Page:
 
 
Detail Page: All information are in the Specs page, and then if we can take the Dealer where available that would be great.
 
 
 
 
 
Sample Schema:
Front Page				Detail Page												
DataDate	Price	Condition	Listing	Vehicle	Make	Model	VIN	Stock	Year	Mileage	BodyStyle	Engine	EngineType	Transmission	DriveTrain	InteriorColor	ExteriorColor	Dealer
1/5/2026	339000	Used	Dealer	2024 Ferrari 296 GTB	Ferrari	296 GTB	ZFF99SLA5R0308194	308194	2024	584 miles	Coupe	3.0L Plug-in Hybrid Twin Turbo V6 818hp 546ft. lbs	-	Automatic	Rwd (rear-wheel drive)	Beige	Blue	Ferrari Los Angeles
 
•	Table name: DUPONTREGISTRY (we want to keep this general in case we need to scrape more combinations)
•	Types: DataDate is date, Price is float, please put everything else as string
•	Primary keys: DataDate, Condition, Listing, Vehicle
 
We would like to scrape this daily. Please let us know if you have any questions.
 
Thanks,
Elliot
 
The information contained in this transmission may contain privileged and confidential information.  It is intended only for the use of the person(s) named above.  If you are not the intended recipient, you are hereby notified that any review, dissemination, distribution or duplication of this communication is strictly prohibited.  This communication is for information purposes only and should not be regarded as an offer to sell or as a solicitation of an offer to buy any financial product, an official confirmation of any transaction, or as an official statement of Junto Capital Management LP.  If you are not the intended recipient, please contact the sender by replying to this e-mail and destroy all copies of this e-mail (and any attachment(s)) from your system.
