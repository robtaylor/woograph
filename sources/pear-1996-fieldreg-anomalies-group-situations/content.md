Journal of Scientific Exploration, Vol. 10, No. 1, pp. 111-141, 1996 

0892-3310/96 © 1996 Society for Scientific Exploration 

## FieldREG Anomalies in Group Situations 

R. D. NEtson, G. J. BRapisH, Y. H. Dopyns, B. J. DUNNE, AND R. G. JAHN Princeton Engineering Anomalies Research, School ofEngineering/Applied Science, Princeton University, Princeton, NJ 08544 

Abstract — Portable random event generators with software to record and index continuous sequences of binary data in field situations are found to produce anomalous outputs when deployed in various group environments. These “FieldREG” systems have been operated under formal protocols in ten separate venues, all of which subdivide naturally into temporal segments, such as sessions, presentations, or days. The most extreme data segments from each of the ten applications, after appropriate correction for multiple sampling, compound to a collective probability against chance expectation of 2x10~. Interpretation remains speculative at this point, but logbook notes and anecdotal reports from participants suggest that high degrees of attention, intellectual cohesiveness, shared emotion, or other coherent qualities of the groups tend to correlate with the statistically unusual deviations from theoretical expectation in the FieldREG sequences. If sustained over more extensive experiments, such effects could add credence to the concept of a consciousness “field” as an agency for creating order in random physical processes. 

. Introduction 

All of the benchmark REG experiments in the PEAR program have been performed with a very sophisticated microelectronic binary generator that incorporates elaborate failsafes, redundancies, and controls to guarantee its nominal randomicity and protection from internal and external bias (Nelson, Bradish, and Dobyns, 1989). With the basic character of the operator-related anomalies well established on this elaborate device (Jahn, Dunne, and Nelson, 1987), however, it became clear that our program, as well as others, would benefit from much simpler REG modules that could enable a broader spectrum of applications of the essential experimental concept. For example, these more compact and less expensive devices could serve as sources for a variety of second and third generation experiments in our own laboratory, facilitate various replication and extension experiments in other laboratories, and enable a number of field studies outside of the laboratory settings. Such portable REG devices have been designed, constructed, and placed into service in numerous experiments in our own laboratory, and several direct replications and extended applications undertaken elsewhere (Nelson, Bradish, and Dobyns, 1992). In all of these, the basic hypothesis that human intention is an essential factor in establishment of the digital anomalies has been re- 

111 

112 

R. D. Nelson et al. 

tained, and this parameter has been treated as the primary correlate in the analyses of the experimental data. 

This portable technology also permits another potentially important genre of experiment, namely the passive monitoring of environmental backgrounds in selected sites and situations where human consciousness might conceivably be altering or organizing a surrounding “field” of potential information, most broadly construed, without specific intention or direct attention to the experimental device by any of the participants. Examples that suggest themselves include religious or secular ceremonies and rituals, individual or group therapy sessions, business meetings, sporting events, professional conferences, or any other group convocations that might include periods of unusually cohesive cognitive interaction, creative enthusiasm, or other forms of emotional intensity. 

This possibility — the establishment of a discernible “consciousness field,” — has been widely proposed in many contexts, by scholars from various disciplines (Basham, 1959; Durkheim, 1961; James, 1977; Sheldrake, 1981). It gains some credence from the informal testimony of our laboratory operators, who frequently speak of achieving a state of “resonance” with the device during successful operation, and from some of the details of their experimental performance. For example, hints of the possible importance of subconscious, - collective, and environmental aspects of the anomalous phenomena, wherein explicit intention is relegated to a secondary or subtler role, arise in the ubiquitous series position effects, in the observed deviations of non-intentional baseline data from chance behavior, in an assortment of gender differences in - performance (Dunne and Jahn, 1995), in the superior performance of some operators when not directly addressing the machines, and in the unusually large effect sizes of co-operator bonded-pairs (Dunne and Jahn, 1993). 

In a systematic attempt to explore this regime, we have deployed FieldREG systems, comprising a portable REG and a notebook computer with appropriate software, as passive background monitors in a variety of group assembly situations where unusual collective dynamics might ensue. In these applications, data are taken in continuous segments, with a time-stamped index identifying scheduled or unscheduled periods of particular interest. The behavior of the system overnight or during extra-session intervals in the meeting schedules provides a form of on-line contro] data. All data are subsequently searched for prolonged segments of unusual behavior, as indicated by extreme shifts in the output means or protracted periods of steady deviation. These anomalies are hypothesized to be indicative of some change in the prevailing information environment associated with the collective consciousness of the assembled group. In a sense, the name “FieldREG” thus acquires a double entendre: i. e., the device has been deployed in a “field” situation, to monitor changes in a consciousness “field.” 

FieldREG Anomalies 

113 

## Equipment 

The portable REG which is the heart of the FieldREG system consists of a printed circuit board and precision components mounted in a 5 x7 x 2 inch cast aluminum box. The random event sequence is based on a low level microelectronic white noise source which is amplified, limited, and ultimately compared with a precisely adjusted DC reference level. At any instant of time the probability of the analog signal equaling or exceeding the reference threshold is precisely 0.5. This white noise signal is sampled 1000 times per second, and the output of a comparator stage is clocked into a digital flip-flop, yielding a stream of binary events, 1 or 0, each with probability 0.5. This unpredictable, continuous sequence of bits is then compared with an alternating template using a logical XOR in hardware, and the matches are counted, thus precluding first-order bias of the mean due to short or long-term drift in any analog component values by inverting every second bit. The resulting sequence is then accumulated as bytes that are transmitted to a serial port of the computer, where they are read and converted to REG data by dedicated software. The digital and analog circuits are isolated from each other spatially and electrically, and the geometry is fixed by the printed circuitry. To avoid electrical cross-talk, digital transmissions are not performed during the analog sampling. Power to the circuits is supplied by an external DC adapter to minimize effects of associated time-varying magnetic fields. In applications where no line voltage is available, power is provided by a battery pack, with the entire system contained in a small carrying case. 

Extensive calibrations of a large number of these portable REG devices indicate that all perform as nominal random sources, with distribution parameters that are indistinguishable from theoretical expectations, or from those of the more elaborate benchmark REG. 

## Computer Software 

The FieldREG data acquisition program runs on a DOS-based computer, usually a laptop portable, and employs many features of the laboratory experiments in order to maintain analytical compatibility with them. For example the software reads the serial port and assembles 25 consecutive bytes as a 200sample trial, from which data are recorded as a sums of 200 bits, with expectation 100, variance 50. The program then generates a data file of consecutive trials, and a corresponding index that contains a new line printed every hour. Interstitial lines record the time, trial number, and other information corresponding to any preset or concurrent marks made using defined function keys to indicate events such as the beginning and end of sessions. A custom analysis program allows specification of the beginning and end of the data sequence to be analyzed, and generates a full statistical analysis of its distribution. A corresponding graph shows the cumulative deviation of the specified data sequence from expectation, marked with a vertical line at each point where a 

114 

R. D. Nelson et al. 

function-key code was entered (see Figure 1). Each such mark is accompanied by a5 percent confidence parabola that starts at the current height of the cumulative trace, allowing a visual assessment of trends corresponding to the identified events or time periods. 

## Protocol 

The two essential requirements for a credible protocol are standardized procedures for specification of potentially interesting periods or events, and welldefined statistical criteria for establishing any non-chance characteristics of the corresponding data. The former necessarily depends to some degree on the particular application, but at a minimum must specify the criteria that objectively identify sessions or events, and the means by which these criteria are implemented, e.g., concurrent notes or marked index lines. For example, preset event markers in the index may be keyed to logbook descriptions of the events; prescheduled events, such as conference talks, field observation periods, or meeting sessions, with or without markers in the index, may be identified from comprehensive, time-stamped notes. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0004-05.png)


**----- Start of picture text -----**<br>
Given an objective identification protocol, the analysis of any apparently<br>unusual or deviant data subset within a given application can be handled by<br>common statistical tests applied to the interval of interest, appropriately cor-<br>rected via Bonferroni adjustments for the prevailing multiple opportunities. In<br>general, to obtain an estimate of the likelihood that a particular segment is evi-<br>be Se Y } Ayr | A<br>9 ay<br>3 LackineYY<br>ok '<br>3<br>é<br>4/6/93, 11:45 15:02 4f193, 9:17 12:04<br>**----- End of picture text -----**<br>


Fig. 1. ICRL: Pilot Study; Vertical lines mark events. 

FieldREG Anomalies 

115 

. 

dence for an anomalous interaction, a Bonferroni adjustment to the individual event probability, p, of the form p, = 1-(1-p)” may be applied, where N denotes the appropriate number of similar opportunities or events. 

In most applications, it is also possible to apply a canonical test for increased variance across all of the subsets within the application, using a sum of squared Z-scores, to compare with the y? distribution (Snedecor and Cochran, 1980). This latter test accurately summarizes the accumulation of evidence for anomalous deviations across all of the data subsets within the application, whereas the Bonferroni adjustment treats a selected segment as a stand-alone anomaly. Thus, in any application where an unusual deviation is exhibited in more than one segment, the Bonferroni procedure will yield a relatively conservative estimate of the degree of anomaly, compared with the ? test. 

## Example Applications 

Formal FieldREG experiments have so far been performed in 10 varied situations, including large and small professional meetings, group gatherings for religious rituals, and certain investigations of unusual sites. The selected data subsets within these databases were chosen on the basis of evidently strong and consistent trends, and their analysis thus requires consideration of the number of similarly defined datasets (e.g., sessions or presentations) that might also have been selected. In all cases, this has been done by adjusting the intrinsic probability of the mean-shift using the Bonferroni calculation described above. In a few examples the ¥? calculation is also given for comparison. 

The first exploration of the FieldREG approach was undertaken at a meeting of the International Consciousness Research Laboratories (ICRL) in April, 1993, albeit without the current FieldREG software. Although this dataset cannot be included in the formal analysis because the recording format and the concurrent documentation do not contain adequate information, it served to suggest the potential value of a carefully implemented protocol. The ICRL group comprises several senior scholars from various scientific disciplines who meet semi-annually to exchange research progress, plan collaborative projects, and discuss the role of consciousness in physical processes. The first of two recorded segments was an afternoon session that consisted primarily of presentations of ongoing research, much of which was deeply engaging for the group, and the FieldREG data showed a steady trend culminating in a significant deviation during the first three hours of this period. The second day’s segment, recorded during pragmatic business discussions in the afternoon session, showed essentially random behavior throughout. Figure 1 displays the total database of approximately nine hours, with two of the vertical lines emphasized to mark particular points; the first is near the end of the three-hour period described above, and the second segregates the two days. (In all of the 

116 

R. D. Nelson et al. 

subsequent examples al] the vertical lines have been removed with the exception of those marking the data segments chosen for further analysis.) 

## ICRLI 

A continuous FieldREG recording using the fully developed protocol and software was made at a three-day ICRL meeting in March 1994. Figure 2a displays the entire data sequence, which includes not only meeting times, but breaks and overnight periods. A vertical line marks the beginning of the third day, anecdotally described as distinctly productive and satisfying. For most of this day, the trend was strongly positive (Figure 2b), and achieved a Z-score of 2.187, corresponding to a Bonferroni-corrected p-value of p,= 0.084 for the selected day’s excursion, suggesting a modestly unusual deviation, even after compensation for multiple sampling opportunities. 

## ICRL II 

A FieldREG recording of one day of an ICRL meeting in December, 1994, is shown in its entirety in Figure 3a with the segment chosen for further analysis marked. Interspersed with various informal discussions and group exchanges, there were three planned, formal presentations of about an hour’s duration, - and the last of these (Figure 3b) showed a rather steady trend culminating in a meanshift with two-tailed p-value of 0.061. The Bonferroni-corrected value in this case is 0.172, indicating that, given the multiple opportunities for chance fluctuations to produce suggestive excursions, it is not highly deviant. Further examination of Figure 3a shows other segments that exhibit strong trends, but these do not correspond to prespecified or objectively identifiable periods, according to the FieldREG protocol. Thus, although they look unusual, they cannot be distinguished from chance fluctuations and hence cannot contribute to our understanding. 

## DMHII 

A group of about a dozen researchers in a working group on Direct Mental and Healing Interactions (DMHI) met for several days in December, 1993. The FieldREG equipment operated for about 35 hours throughout most of the meeting, primarily during the active meeting times but with several unattended periods between sessions when all participants were elsewhere (Figure 4a). In the aggregate, these data look like calibrations of a well-behaved random event generator, as is typically the case for the FieldREG applications. However, there appear to be isolated segments with unusually strong trends that are associated with particular presentation sessions. The most striking of these is shown in Figure 4b, recorded while one researcher spoke for over two hours describing three promising high priority projects. This steady high-going trend has a terminal Z-score of 3.05, corresponding to a two-tailed p-value of 0.002. Over the course of the four days, FieldREG recorded 12 presentations of 

FieldREG Anomalies 

117 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0007-02.png)


**----- Start of picture text -----**<br>
a<br>e 2<br>a<br>:« uh }<br>c<br>§ ‘ . .<br>3| we<br>-’ -2 7<br>; st“iy~Y<br>3/17/94, 9:05 3/19/94, 18:00<br>Fig. 2a. ICRLI: Three-day meeting; last day marked.<br>7<br>M<br>3 ey<br>end<br>owt<br>.bsLytet<br>£<br>4<br>3<br>re<br>£ ee<br>9:07 18:00<br>Fig. 2b. ICRLI: Marked day.<br>**----- End of picture text -----**<br>


118 

R. D. Nelson et al. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0008-02.png)


**----- Start of picture text -----**<br>
a?<br>M<br>a<br>3<br>t<br>3<br>3<br>£<br>mm<br>en Cee ah Wi |<br>4 |<br>pn<br>mI<br>9:14 15:25<br>Fig. 3a. ICRL II: One day; selected session marked.<br>V\/<br>pr<br>Af<br>a go<br>poet<br>- ee<br>———<br>14:35 . 1521<br>Fig. 3b. ICRL II: Marked session.<br>**----- End of picture text -----**<br>


FieldREG Anomalies 

119 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0009-02.png)


**----- Start of picture text -----**<br>
a<br>% he HA avd<br>oy fo<br>» Vy<br>F |<br>"12/6/93, 10:10 12/19/93, 22:18<br>Fig.4a. DMHII: Four-day meeting; selected session marked.<br>0<br>» on<br>FI<br>a<br>‘4<br>aae|<br>aoo<br>10:04 12:28<br>Fig.4b. DMHII: Marked session.<br>**----- End of picture text -----**<br>


120 

R. D. Nelson et al. 

roughly equivalent length, leading to a Bonferroni correction that increases the selected session’s probability to 0.027. 

## DMHL II 

Figure 5a shows a four-day, continuous FieldREG recording made of the December, 1994, DMHI working group meeting, including breaks and overnight periods. This meeting was not broken into defined sessions, but instead was a free ranging discussion focused on research programs. Following an overnight period at the start, the FieldREG trace shows a consistent upward trend during all of the first 12-hour day, culminating in a p-value of 0.014 for the meanshift (Figure 5b). The Bonferroni correction to compensate for selecting one particular day from the four leads to an estimate of p,= 0.055 for this trend to have occurred by chance. 

## CUUPS I 

A FieldREG system with battery pack was provided to a chapter of the Covenant of Unitarian Universalist Pagans (CUUPS) to be used at their ritual gatherings, beginning in December 1993. Under PEAR guidance, the program was introduced to a group of about 35 participants who were told that the FieldREG recordings are intended to explore more systematically the occasional occurrence of anomalous trends in random data that appear to be correlated with group coherence, excitement, enthusiasm, etc. This database includes FieldREG records for six of their ritual gatherings, each nominally an hour long, but with moderate variations in actual length (Figure 6a). Some sessions appear to have unusual, strong trends with reversals during the ritual periods. The example shown in Figure 6b was a full moon ritual, attended by the core members who comprise about a third of the full group. It shows a significant negative trend (Z = —2.557), which, when corrected for the multiple opportunities, yields a p-value of 0.062. 

The x? procedure, mentioned earlier, that evaluates the statistical variance from expectation across all the sessions may be particularly appropriate for this CUUPS example, since all the gatherings are designed rituals with the common purpose of celebrating specific occasions, and may be considered equivalent samples from a particular statistical population. Summing the squared Z-scores yields y?= 12.604, with 6 df, and a p-value for the x? of 0.050. Another estimate for the combined probability can be obtained from 

7 = >-2in P; 

where p; denotes the individual ritual session probabilities, with degrees of freedom equal to two times the number of cases (Rosenthal, 1991). This yields x?= 21.823, on 12 df, and an estimated p-value of 0.039. 

FieldREG Anomalies 

121 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0011-02.png)


**----- Start of picture text -----**<br>
‘<br>t<br>|<br>a<br>12/4/94, 21:18 129/94, 8:38<br>**----- End of picture text -----**<br>


Fig. 5a. DMHIII: Four-day meeting; selected day marked. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0011-04.png)


**----- Start of picture text -----**<br>
3‘ Ww ame ial<br>e<br>&<br>3<br>f<br>a<br>3<br>3<br>£<br>4 oe<br>—————<br>10:00 22:00<br>**----- End of picture text -----**<br>


Fig. 5b. DMHIT: Marked day. 

122 

R. D. Nelson et al. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0012-02.png)


**----- Start of picture text -----**<br>
9 ' 1<br>a nal iad<br>o -4<br>£<br>1 2 3 4 5 6<br>Ritual Number<br>**----- End of picture text -----**<br>


Fig. 6a. CUUPSI: Database for six ritual gatherings; selected session marked. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0012-04.png)


**----- Start of picture text -----**<br>
A<br>~{205<br>20715 21:15<br>**----- End of picture text -----**<br>


Fig. 6b. CUUPSI: Marked Session. 

FieldREG Anomalies 

123 

. 

## CUUPS II 

~ Data were collected in the same manner in a second group of nine CUUPS sessions over the period from June, 1994, to January, 1995 (Figure 7a). The most extreme excursion (Figure 7b) achieved a Z-score of —2.962, and the Bonferroni-corrected p-value is 0.027. In the alternative calculation based on contributions from the full database, the sum of squared Z-scores for all nine sessions results in y7= 20.901, with 9 df, p =0.013. 

## Academy 

The Academy of Consciousness Studies, a two-week multi-disciplinary workshop for some 50 scholars involved in consciousness studies, was held in Princeton during June and July, 1994. The ten days of presentations and discussion offered about 60 sessions from which FieldREG sequences could be selected. One full day is shown in Figure 8a; it includes the most extreme deviation of any session in the 10-day record. This hour-long data sequence is presented in Figure 8b, and corresponds to a discussion, described by several participants as deeply engaging, of the pervasive presence of ritual in human activities ranging from everyday habits, to religion, to science. The calculated intrinsic p-value for this segment is 0.00005, yielding a Bonferroni corrected value of 0.0028. 

## Humor Conference 

Based on an informal hypothesis that humor may have a strong tendency to establish coherent group consciousness, the FieldREG system was used to record the 10th annual Conference on Humor and Creativity, in April, 1995. There were approximately 1000 participants, and over the three day period (Figure 9a), there were five “Keynote” presentations attended by the whole group. Among these, the most extreme deviation was generated during a particularly engaging evening session that ended with a standing ovation followed by an encore. This full session, shown in Figure 9b, had a Z-score of 2.276, and a two-tailed p-value of 0.022, which yields p,= 0.105. 

The conference also included a number of concurrent sessions, thematic break periods, and other pre-defined segments, attended by smaller numbers of participants in separated parts of the convention center. For the 20 defined events, including the Keynote presentations, the x? is 38.995, with 20 degrees of freedom and p;= 0.007, indicating that the FieldREG recorded significantly more extreme deviations during these scheduled periods than expected for a random sequence, and that the effect of the group environment was not limited to the selected Keynote session. 

## SSE Council 

## The FieldREG system was taken to a meeting of the governing Council of 

124 

R. D. Nelson et al. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0014-02.png)


**----- Start of picture text -----**<br>
a<br>M<br>a 4<br>‘ 1<br>A ps f\7 gy<br>|<br>§3 4<br>P<br>|<br>oes<br>|<br>1 23 4 5 6 1 8 9<br>Ritual Number<br>**----- End of picture text -----**<br>


Fig. 7a. CUUPS II: Database for nine ritual gatherings; selected session marked. a 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0014-04.png)


**----- Start of picture text -----**<br>
-4609<br>20:27 21:24<br>Fig. 7b. CUUPS II: Marked Session.<br>**----- End of picture text -----**<br>


FieldREG Anomalies 

125 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0015-02.png)


**----- Start of picture text -----**<br>
yi<br>—l<br>: 4 N<br>c ia<br>sa ot! IN<br>c<br>5<br>ry<br>F]<br>E 7<br>TBN4, 9:10 18:00<br>**----- End of picture text -----**<br>


Fig. 8a. Academy: One full day, of ten; selected session marked. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0015-04.png)


**----- Start of picture text -----**<br>
a ae<br>M oe<br>4909<br>15:04 1557<br>**----- End of picture text -----**<br>


Fig. 8b. Academy: Marked session. 

126 

R. D. Nelson et ai. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0016-02.png)


**----- Start of picture text -----**<br>
¥a a<br>a<br>8Li; ©. a<br>‘<br>ry<br>3<br> -2 aN Py<br>N iy<br>4/28/95, 15:13 4/30/95, 14:39<br>**----- End of picture text -----**<br>


Fig. 9a. Humor Conference: Three days; selected session marked. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0016-04.png)


**----- Start of picture text -----**<br>
2<br>————<br>20:15 21:25<br>Fig. 9b. Humor Conference: Marked session.<br>**----- End of picture text -----**<br>


FieldREG Anomalies 

127 

_ 

the Society for Scientific Exploration (SSE) in December, 1994, where its purpose was described in a short introduction, and it was deployed in a demonstration application. The seven-hour meeting (Figure 10a) had no formal session structure, but the agenda, together with notes of times allotted to major issues, allowed the definition of 12 topical segments varying in length from 15 to 50 minutes. The most extreme deviation exhibited among these was during a 20 minute discussion on the development of a World Wide Web homepage for SSE and its journal (Figure 10b). The associated probability was 0.052, but the Bonferroni adjustment raises this to p,= 0.473, indicating the deviation was not unusual given the number of opportunities present in the database. Computing the x? for the 12 segments further confirms the random character of these data, yielding 7?= 10.175, with 12 df, and p = 0.601. 

## Marfa Lights 

In addition to group applications like those just shown, the FieldREG system may be useful as a background monitor in other environments of interest. In one such example, three ICRL researchers included a FieldREG system as part of the instrumentation taken to the Big Bend area of western Texas to record a variety of physical parameters that might correspond to the appearance or activity of the anomalous “Marfa lights” reported in that area. On six successive nights, recordings of approximately two hours duration were taken (Figure 11a), one of which showed a consistent trend (Figure 11b) with an associated Z-score of 2.031. Although there were no corresponding anomalous light phenomena, the logbook notes describe a “deep and occasionally humorous conversation” that took place while the researchers sheltered from inclement weather. The Bonferroni correction yields a probability for this session of pg= 0.228. 

## Combined Results 

In attempting any concatenation of the individual experiments listed above into an overall statistical likelihood, it is first necessary to acknowledge that two categories of selection have been invoked in several of the applications, i.e., the session or presentation, and the day. Again, a form of Bonferroni correction may be applied, yielding a scale-corrected p-value of 1~(1—p,)* for those applications where both scales of analysis were available. The results for all 10 applications are summarized in Table 1. The composite value across all these applications, calculated from ; 

x = L-2in pp, 

with 2N degrees of freedom (Rosenthal, 1991) yields y?= 50.008, with 20 df, and a corresponding composite p-value of 2 x 10~. The accumulation of modest but consistent correlations with group dynam- 

128 

R. D. Nelson et al. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0018-02.png)


**----- Start of picture text -----**<br>
_—<br>|<br>‘ |<br>aJ<br><|<br>y<br>Pya ronMt  :|<br>4 alll<br>|<br>10:05 16:20<br>**----- End of picture text -----**<br>


Fig. 10a. SSE Council: Business meeting; selected session marked. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0018-04.png)


**----- Start of picture text -----**<br>
¥<br>”<br>a<br>SS,Ta<br>wow<br>14:15 14:35<br>**----- End of picture text -----**<br>


Fig. 10b SSE Council: Marked session. 

FieldREG Anomalies 

129 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0019-02.png)


**----- Start of picture text -----**<br>
ty f<br>: Vi<br>a q /}<br>oh<br>i AW ><br>Fa]<br>£<br>1 2 3 4 5 6<br>Day<br>1la. MarfaLights: Field investigation, investigation, six sessions; selected session session marked.<br>1800<br>aN ee<br>LAS<br>4800-<br>20:59 23:56<br>Fig. 11b. Marfa Lights: Marked session.<br>**----- End of picture text -----**<br>


Fig. 1la. MarfaLights: Field investigation, investigation, six sessions; selected session session marked. 

130 

R. D. Nelson et al. 

ics seen in the FieldREG data should be compared with appropriate control data, as well as with the theoretical chance expectation. Ideally these should be generated in the same or similar circumstances to those of the active data. However, the full databases for only about half of the applications presented here include extensive subsets from break periods and overnight recording; the others consist primarily of active data, e.g., many of the CUUPS sessions have only a few minutes before and after the rituals, and the Council example has no extra-session data that can be invoked for control purposes. Thus, we are forced to a hyper-conservative approach for creating controls, based on random resampling of the full databases, a procedure which is likely to include by chance some portions of the active, deviant subsequences. Specifically, the ‘full database in each example is resampled using a single set of random incursions into the actual data sequence to generate the appropriate number of control “sessions,” each of the same length as the active FieldREG segment selected from that application. Thus, the randomly extracted control data correspond to no particular events or time periods, whereas the FieldREG data are delineated by the start and endpoints of specific sessions. The most extreme deviation found among the several control segments generated for each of the ten applications was identified, and p, was calculated, using the same procedures as for the actual data. Table 2 shows the results, to compare with those in Table 1. (Parentheses around the application names denote calibration data.) 

Although several of the randomly drawn control subsets have low intrinsic p-values, as might be expected given the selection of the most deviant segments from a large number of random sequences, the Bonferroni adjustment renders most of these cases unimpressive. The x’ for the composite of the control applications is 19.950, with 20 df, corresponding to a p-value of 0.461. 

In a less conservative alternative control procedure, the same resampling process was applied to data generated by a portable REG device undergoing calibrations in the laboratory. Table 3 shows these calibration-based control results in the same format as the active data and the random resampling controls. Again, the selected segments show small p-values, but after correction, most of these are moderate, and the x? for the composite of the control examples is 26.476, with 20 df, corresponding to a p-value of 0.151. 

In Figure 12, the x? values for the individual applications (solid line) as well as the random controls extracted from the field data and from the laboratory calibrations (dashed lines) are plotted as cumulative sums over the ten independent examples. The figure also includes smooth dotted lines that represent the chance expectation for this sum as well as the locus of a significant departure (p = 0.05) from that expectation. While both sets of contro] data deviate only by small amounts across the accumulation of the ten datasets, the actual data showa clear trend that culminates in a highly significant deviation, with p=2x10~. 

131 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0021-01.png)


**----- Start of picture text -----**<br>
|||||||||
|---|---|---|---|---|---|---|---|
|-|FieldREG|Anomalies|
|TABLE|1|
|Active FieldREG Data|
|Application|Trials|Cases|Extremep|Bonf.p,|Scale-Corr. pz|
|1.|ICRLI|36745|3|0.029|0.084|0.161|
|2.|ICRLI|2401|3|0.061|0.172|0.315|
|3.|DMHII|9922|12|0.002|0.027|0.054|
|4.|DMHI Ii|49629|4|0.014|0.055|0.055|
|5.|CUUPS|I|4136|6|0.0i1|0.062|0.062|
|6.|CUUPS|II|3905|9|0.003|0.027|0.027|
|7.|Academy|3674|60|0.00005|0.003|0.006|
|8.|Humor Conf.|4825|5|0.022|0.105|0.105|
|9.|SSE Council|1378|12|0.052|0.382|0.382|
|10.|Marfa Lights|12194|6|0.042|0.228|0.228|

**----- End of picture text -----**<br>


TABLE 2 

Control Data from Random Resampling 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0021-04.png)


**----- Start of picture text -----**<br>
||||||||
|---|---|---|---|---|---|---|
|Application|Trials|Cases|Extreme p|Bonf. pz|Scale-Corr.pg|
|1.|QCRLI)|36745|3|0.352|0.728|0.926|
|2.|(UCRLT)|2401|3|0.060|0.121|0.227|
|3.|(DMHID|9922|12|0.152|0.862|0.981|
|4.|(DMBHTIT)|49629|4|0.042|0.219|0.219|
|5.|(CUUPSD|4136|6|0.002|0.012|0.012|
|6.|(CUUPS I)|3905|9|0.094|0.589|0.589|
|7.|(Academy)|3674|60|0.004|0.214|0.382|
|8.|(Humor Conf.)|4825|5|0.158|0.577|0.577|
|9.|(SSE Council)|1378|12|0.090|0.678|0.678|
|10.|(Marfa Lights)|12194|6|0.464|0.976|0.976|

**----- End of picture text -----**<br>


TABLE 3 

Control Data from Laboratory Calibrations 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0021-07.png)


**----- Start of picture text -----**<br>
|||||||||
|---|---|---|---|---|---|---|---|
|Application|Trials|Cases|Extreme p|Bonf. pz|Scale-Corps|
|1.|(ICRL I)|36745|3|0.004|0.011|0.022|
|2.|(ICRL It)|2401|3|0.002|0.007|0.014|
|3.|(DMHID|9922|12|0.023|0.248|0.434|
|4.|(DMHI 1)|49629|4|0.168|0.521|0.521|
|5.|(CUUPS|I)|4136|6|0.541|0.991|0.991|
|6.|(CUUPS|II)|3905|9|0.074|0.500|0.500|
|7.|(Academy)|3674|60|0.007|0.359|0.590|
|8.|(Humor Conf.)|4825|5|0.448|0.949|0.949|
|9.|(SSE Council)|1378|12|0.016|0.177|0.177|
|10.|(Marfa Lights)|12194|6|0.123|0.544|0.544|

**----- End of picture text -----**<br>


132 

R. D. Nelson et ai. 


![](sources/pear-1996-fieldreg-anomalies-group-situations/images/pear-1996-fieldreg-anomalies-group-situations.pdf-0022-02.png)


**----- Start of picture text -----**<br>
50<br>40 FieldREG Data<br>xX» 30 aes= .05<br>ee wert<br>20 : valine 7<br>Control, Cali. = Cuan or enn rried<br>“aog , fawn/poreeeeeeExpectatio: [ay]<br>gee<br>0 2 4 6 8 10<br>Application Number<br>**----- End of picture text -----**<br>


Fig. 12. Cumulative x? for ten FieldREG applications; active data compared to controls. 

## Effect Size 

For the composite database, the normal deviate, or Z-score, corresponding to the final p-value is Z = 3.540. The striking Academy example (after the Bonferroni and scale corrections) has a normalized deviation of Z = 2.512. Beyond such basic statistical figures of merit, it is illuminating to examine various other indicators of absolute effect size. The simplest of these is the fraction of bits that have been altered from the chance expectation of equipartition, most conveniently expressed as Z per bit equals Z/N,’” or equivalently, 2 x Ap where N, is the number of bits processed, and Ap is the difference of the observed p from theoretical expectation. In the laboratory REG experiments this effect size is on the order of 0.0002 for the full database of 2.6 million trials, and as large as 0.002 for certain subsets. A conservative approximation of corresponding values for the FieldREG database of 0.8 million trials, calculated from the Z-score associated with the Bonferroni adjusted p-value and the total number of bits across all sessions, yields effect sizes of 0.0003 for the combined result, and 0.0004 for the Academy example. The CUUPS examples both have larger Z per bit effect sizes of 0.0007. 

We may also calculate a somewhat different effect size that enables comparison across a variety of different laboratory experiments, by normalizing the size of the anomalous effect in terms of the amount of time spent attempting to achieve it (Nelson, 1994). For example, an effect size per hour is calculated as E,, = Z/N,'? where Z is the normal deviate corresponding to the p-value, and N, is the number of hours in the selected session. These time-based effect sizes in 

FieldREG Anomalies 

133 

the REG experiments, and indeed in most of our human/machine interaction experiments, average about 0.2, and range up to about 0.8 for bonded co-operator pairs. In the FieldREG applications, the average time-based effect size is about 0.3, with the largest effect size 0.7 (CUUPS I or II). Thus, these effect sizes for the group applications appear to be similar to those seen in the laboratory REG experiments. We should note that because the Bonferroni adjustment is highly conservative, both the Z per bit and time-based effect size estimates err on the small side, by about 10 percent to 30 percent, with larger error as the database size increases. 

## Discussion 

These FieldREG data comprise a consistent empirical indication of anomalous behavior of a random physical system located in the presence of groups of people engaged in shared cognitive or emotional activity. All but one of the ten applications (the SSE Council meeting) make positive contributions to the highly significant overall deviation from expectation. Five of the ten applications independently achieve deviations approaching or exceeding the conventional p < 0.05 criterion for statistical significance, despite the conservative Bonferroni adjustment. Because this research protocol is new and the data sparse, any mechanistic interpretation is risky at this point, but some implications for more incisive future research are evident. In particular, a number of technical, phenomenological, and philosophical questions merit further consideration, among them: 

1. What is the relationship of these non-intentional group effects to those observed in the standard laboratory-based REG experiments, where specified individuals deliberately endeavor to influence machine outputs in accordance with pre-stated intentions? 

2. Does the direction of an anomalous response trend have any physical or psychological implications? 

3. Are the anomalous segments attributable to the experimenter, or to specific individuals in the group, or is the effect intrinsically collective in nature? 

4. What emotional, intellectual, or physical characteristics of the group environment contribute to the effect? 

5. Is the concept of a “consciousness field” viable and testable? 

6. Can an effective theoretical model be developed? 

7. What other applications of FieldREG might be productive? 

8. What are the broader scientific and cultural implications of the phenomena represented by the FieldREG results? 

Clearly our present FieldREG database is far too limited in scope and scale to allow any definitive response to these questions at this time. Replication of these and similar experiments by other investigators is needed and has indeed begun (Radin, 1996; Blasband, 1995), but much more data covering a broader 

134 

R. D. Nelson et al. 

range of group situations will be required before the fundamental character of these effects is likely to emerge. Nonetheless, a little modest speculation on these issues even at this early stage may help to define more illuminating experiments and models, and may encourage others to join in study of the problem: 

## Comparison with Laboratory REG Studies 

By far the largest body of REG data acquired in our laboratory has been generated by individual operators located proximate to a sophisticated microelectronic REG, attempting to influence the mean of its binary output distribution toward higher or lower values than the baseline, calibration, or theoretical values, in accordance with pre-recorded conscious intentions. The scale of these results, their operator-specific character, their dependence on secondary parameters, and their internal structure have been thoroughly established, replicated, and documented (Jahn, ez al., 1987; Nelson, et al., 1991). But the technology, protocol, and analysis of the FieldREG experiments differ from these benchmark experiments in a number of potentially important aspects. First, the portable REGs employed here are much simpler devices, unencumbered by many of the redundancies and failsafes of the benchmark machine. Although these units have been thoroughly calibrated and routinely employed for many experiments within the laboratory and invariably found to be competent random sources for such studies, indistinguishable in their performance from the much more elaborate machine, their simplicity and small size endow their experimental applications with a considerably less explicit technological ambience. Second, the number of human participants involved in the FieldREG studies usually is much greater than in the laboratory experiments. Although we have some prior experience with “co-operator” pairs in the laboratory, and indeed have found some intriguing results from these (Dunne, 1991), we have only a few viable databases encompassing larger groups. Perhaps most important, however, is the absence of any explicit, or even implicit intention on the part of the group members with respect to the FieldREG output. In most cases the participants are only peripherally aware of the machine, and have little understanding of its technical operation or purpose. 

Two experimental excursions that might illuminate these distinguishing factors suggest themselves: 1) A more substantial program of larger group experiments performed within the standard laboratory REG protocols; and 2) FieldREG experiments wherein explicit pre-stated intentions are deliberately imposed by or on the group. Comparison of the results of such studies with those reported above and with the benchmark data could help focus interpretation of the phenomena onto its most salient aspects. 

## Direction of the Anomalous Response 

Although most of the laboratory-based protocols are explicitly directional 

FieldREG Anomalies 

135 

in a tripolar form, e.g. “high/low/baseline,” a few more recent experiments are, by their nature or by experimental choice, bipolar, e.g., “effect/no effect.” This latter form of “intention” is inherently more permissive and relaxed in not requiring a given direction of response. Rather, in these studies we search for any extraordinary excursions of the distribution mean, without regard for direction. Such protocols are probably more amenable to comparison with the FieldREG situations, and will be pursued in ongoing experiments and analyses. Also possibly instructive are the observed distinctions in polarity of response between male and female operators (Dunne, 1996). Complementary studies could attempt empirical correlation of the polarity of anomalous FieldREG excursions with the gender mix of the group, as well as with other technical and subjective indices. In all of this, it should be borne in mind that the portable REG used inthe FieldREG work, like its benchmark predecessor, includes a hardware algorithm that eliminates any direct correspondence between the electrical polarity of the sampled noise and the ultimate binary events. That is, the output polarities relate only to the information produced by the composite machine, not to the response of its physical noise source, per se. 

## Individual vs. Collective Sources of the Effects 

An important factor to discriminate via further studies is the relative importance of the group dynamic, vis-a-vis a dominating influence of one or more individual participants. For example, should an anomalous trace acquired during the course of a stimulating lecture be attributed to the lecturer, to the topic, to the collective involvement of the audience, or even to the experimenter, who clearly has an interest in the acquisition of interesting data? Similarly, is the response to a communal ritual driven by its format, by the interpersonal resonances it engenders, or by one or more particularly strong individual responses to the situation? In an extreme view, one might even regard the REG system itself as a participant in such exercises, capable of reacting to diverse stimuli in some characteristic fashion of its own. Empirical discrimination among these conceptual models will be difficult at best, and perhaps fundamentally impossible if the processes are intrinsically holistic. Short of elaborate permutations of participants among many otherwise similar sessions in an attempt to isolate individual drivers of the effects, few incisive experiments suggest themselves, and this issue may have to be left unexplored in deference to more readily testable hypotheses. With regard to the experimenter as source, our design allows individuals not associated with the PEAR laboratory (and not experimenters in the strict sense) to install and operate the FieldREG equipment. For example, the CUUPS applications are managed by a member of that group, with no direct oversight on the part of PEAR lab staff beyond an initial tutorial. Their results are among the strongest in the database, and this suggests, at least tentatively, that the nominal experimenter is not a necessary source of influence. 

136 

R. D. Nelson et ai. 

## Emotional, Intellectual, and Physical Corrrelates 

In contrast to the previous item, correlations of the FieldREG effects with independently specifiable characteristics of the group composition, agenda, purpose, tone, context, success, etc., could more readily serve to identify the effective factors stimulating the observed response anomalies. Although many of these discriminators may be unavoidably subjective, and some of them may not be specifiable until the sessions are complete, all could be noted in some self-consistent format prior to examination of the data. 

While it is difficult to use anecdotal observations in a rigorous way, these may help to formulate specific questions and hypotheses for further experiments. For example, in the Academy session shown in Figure 8b, the steeply inclined central portion is associated with an intense, twenty-minute discussion of the ubiquitous presence of ritual in everyday life, by two individuals giving examples that were personally important but easily acknowledged by other participants. Logbook notes and concurrent tape recordings independently confirm that there was a perceived special quality of shared and coherent attention during this session, summarized in a spontaneous remark by one participant: “I don’t know if others had the same experience, but there was a very noticeable change in the energy here. It feels like an affirmation of the importance of what’s going on.” 

In the examples from the CUUPS group, there are an number of similarities in the two independent batches of data. Both of the extreme sessions were recorded during full moon rituals, the trend in both cases is toward lower scores, and the magnitudes of the deviations are quite similar and considerably larger than those in the other sessions. The CUUPS group member who is responsible for the FieldREG project expresses no surprise at finding the full moon sessions stronger because, “On the whole, our sabbats are not very personal or intense, whereas the moons sometimes are.” 

Some insight also may be gained from applications in other contexts. For example, Blasband (1995) reports that an REG system present during psychiatric therapy sessions shows consistent, significant trends of opposite polarity when the data are segregated into categories corresponding to the emotional responses of anxiety or anger, whereas segments associated with “just talking” show no notable or consistent deviation. Similarly, the relatively bland business meeting of the SSE Council is the only application thus far that has not yielded a positive contribution to the aggregate evidence for an effect of the group situation on the REG. 

All of these examples suggest a testable hypothesis regarding the dependence of the FieldREG response on its venue of application, namely: an environment fostering relatively intense and general cognitive or emotional engagement will yield more vigorous responses than relatively mundane or pragmatic assemblies. 

FieldREG Anomalies 

137 

## Consciousness Field 

One conceptual hypothesis for the group-related anomalies indicated by FieldREG is that the emotional/intellectual dynamics of the interacting participants somehow generate a coherent “consciousness field,” to which the REG responds via an anomalous decrease in the entropy of its nominally random output. In principle, one might attempt to strengthen this premise by mapping the spatial and temporal dependence of the response amplitude and character throughout the immediate convocation area and possibly beyond, but here we encounter certain empirical and theoretical complications. Namely, the wellestablished remote database from our laboratory REG experiments shows no Statistically significant dependence of effect size on the physical separation of the operator from the machine, up to global distances, and likewise no dependence on the temporal interval between operator effort and actual operation of the target machine, up to several days, plus and minus (Dunne and Jahn, 1992). Therefore, if the group FieldREG effects draw from the same basic phenomena as the laboratory experiments, no conceptual models based on currently known physical fields with their usual 1/r’ dependencies and very __ limitedHowever, advancedthe andconcept retardedof asignalconsciousnesscapabilitiesfieldare likelyneed notto suffice.be completely bound by traditional physical constraints. The results of our benchmark experiments suggest that the basic effects are analytically tantamount to small changes in the elemental binary probabilities underlying the otherwise random distributions (Jahn, Dobyns, and Dunne, 1991) and the nonlocal effects demonstrated in the remote REG data further indicate that these anomalies may be more informational than dynamical in their physical character. As developed in several other references, generalization of the inherent human concepts of “distance” and “time” to encompass subjective as well as objective aspects can be a profitable, indeed powerful, strategy for representation of many forms of conscious experience, both normal and anomalous (Jahn and Dunne, 1986). In such a generalized perspective, simple physical separation is replaced by some form of attentional or emotional proximity to the device in the mind of the operator, and the locus and extent of physical time are replaced by some specification of attentional focus and intensity of subjective investment. Thus, any group consciousness field would more likely be conditioned -by such subjective parameters relative to the participants and their agenda, rather than by their physical configuration or by physical time. One test of this radical hypothesis would be to remove the FieldREG unit from the assembly area to some remote location while still dedicating its operation to the group event. The recipe for this dedication is far from clear, but the protocol invoked in the laboratory remote REG experiments would seema reasonable first format (Dunne and Jahn, 1992). The goal again would be to seek correlations of the anomalous responses of the remote machine with specifically indexed events in the convocation. Extension of the tests to “off-time” protocols invoking temporal as well as spatial displacement could also be con- 

138 

R. D. Nelson et ai. 

sidered, but here the problem of indexing the output traces for correlations with sequential features of the meeting could become very difficult. 

## Theoretical Models 

The invocation of a consciousness “field” is but one aspect of the composition of a comprehensive theoretical model of the FieldREG phenomena. Even for the laboratory based experiments, the inescapable need to specify a host of potentially relevant subjective parameters and incorporate them into viable analytical formalisms severely strains the usual scientific requisites of standardization and quantification, well before any apt conceptual framework can be specified. At this point in our understanding, only frankly metaphoric, semiquantitative models have been assembled, but a few of these have had some utility in cataloguing data sets, verbalizing conceptual distinctions, and guiding subsequent experiments. One such model (Jahn and Dunne, 1986), although primarily addressed to binary human/machine or human/human interactions, also lends itself to situations like those addressed in this paper. This model actually proposes group consciousness properties, defined by analogy to various statistical physical effects, among them certain natural group “resonances.” Whether such subjective specifications of given assemblies will be useful indicators for interpreting or generating FieldREG effects, or for deSigning future experiments and interpreting data from them, remains to be seen. 

## Technical Applications 

If FieldREG is indeed functioning as a monitor of the subjective character of the group interactions to which it has been applied, a broad range of extensions suggest themselves, some of which could be instructive for better understanding of the phenomenon, others of which could hold pragmatic benefits. In the former category, deployment within a variety of formal and informal religious services, large sporting events, and political rallies are obvious candidates for situations with a tendency toward group coherence. Placement in complex social environments that have more chaotic group dynamics, e.g., shopping mall crowds or subway stations, could provide an instructive contrast. Among the potential pragmatic benefits, monitoring of counseling or healing sessions could conceivably correlate with the efficacy of the treatments (Blasband, 1995); applications in business or industrial settings might forewarn of counterproductive personnel interactions and suggest improved configurations; in educational contexts, the more effective pedagogical techniques could be indicated; in military or emergency service arenas, stress reduction in crisis situations might be facilitated. Realization of any of these possibilities will clearly require much better basic comprehension of the fundamental process. 

FieldREG Anomalies 

139 

## Scientific and Cultural Implications 

Some attempts have been made to assess the broader implications of the anomalous phenomena evidenced in our laboratory-based experiments and suggested by concomitant theoretical models, within the three overlapping contexts of physical science, applied technology, and personal and public affairs (Jahn and Dunne, 1987). The FieldREG results and potentialities discussed above prompt some extension and refinement of each category of these speculations: 

In the domain of basic science, the inescapable need to include consciousness as a proactive ingredient in any comprehensive model of physical reality is further underscored by the group results that, on the one hand, relax the requisite of directed intentionality and, on the other, suggest some field-like character for the phenomena. These two aspects, coupled with numerous technical and subjective indications from our laboratory-based experiments, suggest that this capacity of consciousness is not so much associated with cognitive functions or other higher brain activities, as with more primitive limbic drivers of our behavior. If this is correct, the implications for its understanding and utilization may differ profoundly from those for more commonly recognized cortically-based capabilities of consciousness. 

With respect to the arenas of modern technology, the same concerns for the vulnerability of delicate information processing equipment to disruptive human/machine anomalies that originally motivated establishment of our research program must now be extended to encompass larger group effects and less deliberate intentions. Conversely, the opportunities for positive exploitation of constructive human/machine interactions for more effective engineering systems may be enhanced by the group possibilities. 

Finally, and perhaps most importantly, beyond any scientific impact or technological application, clear establishment of a salient role for group consciousness in the establishment of reality could hold sweeping implications for our collective and individual views of ourselves, our relationships to others, and to the world in which we exist. These, in turn, could impact our values, our priorities, our sense of opportunity and responsibility, and our entire style of life. 

## Conclusion 

To recapitulate our present position, it appears that sufficient early data have been accumulated from FieldREG deployments in a variety of group situations to establish that these rudimentary, binary electronic information processors are responding with anomalous outputs to some aspects of the prevailing interpersonal environments. Any attempt to specify the group/machine dynamics that manifest in these anomalies clearly should await much more extensive and incisive empirical data, but the absence of directed intentionality in these applications would seem to complicate further the formulation of vi- 

140 

## R. D. Nelson et al. 

able theoretical models of anomalous human/machine phenomena. Beyond this, the ultimate implications for scientific epistemology, for technological applications, and for personal and collective cultural affairs may need to be broadened. Perhaps most consequential is the possibility that the concept of a consciousness “field,” heretofore postulated in various abstract forms by scholars of many disciplines, may now be on the threshold of rigorous scientific demonstration as a driver of physical] reality. 

## Acknowledgements 

The authors are indebted to the individuals and groups who have allowed us to record data during private meetings and gatherings. The Princeton Engineering Anomalies Research program is supported by grants from Mr. Laurance S. Rockefeller, Mr. Donald Webster, the McDonnell Foundation, the George Ohrstrom Foundation, and the Fetzer Institute. 

## References 

Basham, A. L., (1959). The Wonder That Was India. New York: Grove Press. 

- Blasband, R. (1995). Personal communication. Also presented at the 1995 convention of the Society for Scientific Exploration, Huntington Beach, CA. 

- Dunne, B. J. (1991). Co-operator experiments with an REG device. Technical Note PEAR 91005, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Dunne, B. J. (1996). Gender differences in human/machine anomalies. Technical Note PEAR 96001, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Dunne B. J. and Jahn, R. G. (1992). Experiments in remote human/machine interaction. Journal of Scientific Exploration, 6, 311. 

- Dunne B. J. and Jahn, R. G. (1993). Consciousness, randomness, and information. Technical Note PEAR 93001, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Dunne B. J. and Jahn, R. G. (1995). Consciousness and anomalous physical phenomena. Technical note PEAR 95004, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Durkheim, E. (1961). Society and individual consciousness. In T. Parsons, E. Shils, K. D. Naegele, and J. R. Pitts (Eds.), Theories of Society, Vol. 2, 720. Glencoe, Illinois: The Free Press. 

- Jahn, R. G. and Dunne, B. J., (1986). On the quantum mechanics of consciousness, with application to anomalous phenomena. Foundations ofPhysics, 16,721. 

- Jahn, R. G., Dunne, B. J., and Nelson, R. D. (1987). Engineering anomalies research. Journal of Scientific Exploration, 1,21. 

- Jahn, R. G. and Dunne, B. J., (1987). Margins ofReality: The Role of Consciousness in the Physical World. New York: Harcourt Brace. 

- James, W. (1977). Human Immortality. Boston: Houghton-Miffin. (Originally published 1898). Nelson, R. D., Bradish, G. J., and Dobyns, Y. H. (1989). Random event generator qualification, calibration, and analysis. Technical Note PEAR 89001, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Nelson, R. D., Dobyns, Y. H., Dunne, B. J., and Jahn, R. G. (1991). Analysis of variance ofREG experiments: Operator intention, secondary parameters, database structure. Technical Note PEAR 91004, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

141 

, 

## FieldREG Anomalies 

- Nelson, R. D., Bradish, G. J., and Dobyns, Y. H. (1992). The Portable PEAR REG: Hardware and Software Documentation. Internal Document #92-1, Princeton Engineering Anomalies Research, Princeton, NJ. 

- Nelson, R. D. (1994). Effect size per hour: A natural unitfor interpreting anomalies experiments. Technical Note PEAR 94003, Princeton Engineering Anomalies Research, Princeton University, School of Engineering/Applied Science. 

- Radin, D. I. (1996). Anomalous organization of random events by group consciousness: Two exploratory experiments. Journal of Scientific Exploration, 10, 1, 143. 

- Rosenthal, R. (1991). Meta-Analytic Procedures for Social Research (Revised ed.). Newbury Park, CA: Sage. 

- Sheldrake, R. (1981). A New Science ofLife: The Hypothesis ofFormative Causation. Los Angeles, CA: J. P. Tarcher, Inc. 

- Snedecor, G. W. and Cochran, W. G. (1980). Statistical Methods, Seventh Edition. Ames, Iowa: Iowa State University Press. 

