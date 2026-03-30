Journal of Scientific Exploration, Vol. 6, No. 1, pp. 23-45, 1992 

0892-3310/92 ©1992 Society for Scientific Exploration 

## On the Bayesian Analysis of REG Data 

York H. Dosyns Princeton Engineering Anomalies Research Princeton University, Princeton, NJ 08S44 

Abstract—Bayesian analysis may profitably be applied to anomalous data obtained in Random Event Generator and similar human/machine experiments, but only by proceeding from sensible prior probability estimates. Unreasonable estimates or strongly conflicting initial hypotheses can project the analysis into contradictory and misleading results. Depending upon the choice of prior and other factors, the results of Bayesian analysis range from confirmation of classical analysis to complete disagreement, and for this reason classical estimates seem more reliable for the interpretation of data of this class. 

## Introduction 

The relative validity of Bayesian versus classical statistics is an ongoing argument in the statistical community. The Princeton Engineering Anomalies Research program (PEAR) has heretofore used classical statistics exclusively in its published results, as a matter of conscious policy, on the grounds that the explicit inclusion ofprior probability estimates in the analysis might divert meaningful discussion of experimental biases and controls into debate over the suitability ofvarious priors. Nonetheless, Bayesian analysis can offer some clarifications, particularly in discriminating evidence from prior belief, and is therefore worth examination. 

In this article we apply the Bayesian statistical approach to a large body of random event generator (REG) data acquired over an eight-year period of experimentation in the human/machine interaction portion of the Princeton Engineering Anomalies Research (PEAR) program. When assessed by classical statistical tests, these data display strong, reproducible, operator-specific anomalies, clearly correlated with pre-recorded intention and, to a lesser degree, with a variety of secondary experimental parameters (Nelson, Dunne, and Jahn, 1984). When assessed by a Bayesian formalism, the conclusions can range from a confirmation of the results of the classical analysis with essentially the same p-value against the null hypothesis, to a confirmation of the null hypothesis at 12 to 1 odds against a suitably chosen alternate, depending on how the analysis is done and what hypotheses are chosen for comparison. 

The intent ofthis paper is to examine both the range ofconclusions possible from Bayesian analysis as applied to a specific data set and the implications 

23 

24 

## Y. H. Dobyns 

of that range. The empirical meaning of families of prior probabilities that lead to related conclusions is of particular interest. We will also examine the relation between Bayesian odds adjustments and classical p-values in light of considerations of statistical power and the likelihoods of what a classical statistician would call ‘““Type I” and “Type IT” error. (At various times it will be necessary to contrast Bayesian with non-Bayesian approaches which are variously called “‘frequentist”, ““Fisherian”’, or “‘sampling theory” statistics. While acknowledging that non-Bayesian statistics are a conglomerate category on the order of “nonelephant animals,” for purposes of this discussion any analytical approach that does not include an explicit role for subjective prior probabilities will be called “‘classical.”’) 

## Elementary Bayesian Analysis 

Bayes’ theorem (p(6| y)p(y) = p(y|@)p(6)) is a fundamental result of probability theory from the properties of contingent probabilities. Its analytical application is that of revising prior probability estimates in light of evidence, that is, of determining the extent to which various possibilities are supported by a given empirical outcome. In the most basic application of Bayesian analysis one is assumed to have a model or hypothesis with one or more adjustable parameters @. One’s state of prior knowledge, or ignorance, may be expressed as a prior probability distribution 7(0) over the space ofpossible 6 values. It is further assumed that some method exists by which a probability a(y|6) can be computed for any possible experimental outcome y, given a definite parameter value @. In standard REG experiments, for example, 6 consists of a single parameter, the probability p with which the machine generates a hit in an elementary Bernoulli trial. The probability of exactly s successes in a set of 7 trials is then given by the binomial formula 

a(n, s\p) = ("\ra ~ pyr (1) 

where (") is the combination of m elements taken s at a time, namely n!/[s!(n — s)]. 

By Bayes’ theorem, Equation (1) may alternately be regarded as the probability of a parameter value p, given actual data m and s. When cast in this form, « is more commonly called the likelihood, 2. The general recipe for updating one’s knowledge of parameter(s) @ in light of evidence y is expressed by 

my) « Ql y}r(4) (2) where 7,(6|y) is the posterior probability distribution among possible values for 6, given the prior distribution z, and the likelihood 2. For the case of REG data, 

Bayesian REG analysis 

25 

# m(p|n, s) « &p|n, 5)a(p) = ("\ra ~ py"-*x(p). (3) 

Note that (2) and (3) are expressed as proportionalities rather than equalities. While there is always a normalization for 2 such that 2(@| y)x(6) has a total integral of 1, this normalization in general depends on z,(6). Specifically, the use ofLl y) = 26)y)/ {é d62(6 | y}r,(6), where f6 denotes integration over all possible values of 6, produces the correct normalization. The relations (2) and (3), on the other hand, express 2 purely as a function of y and 6 without reference to prior probabilities. The conceptual clarity of stepping from one state of knowledge about 6, or probability distribution over 6, to another, with the aid of a quantity that depends only on objective evidence, thus entails the cost of renormalizing the posterior probabilities to a total strength of 1 as the last step in the calculation. 

Since it is already a proportionality, expression (3) may be simplified to 

«\(p\|n, Ss) x pl — p)"-*ao(p) (4) 

where the combinatorial factor, lacking p dependence, has been subsumed into the normalization. This form illustrates an important feature of Bayesian analysis. After prior probabilities have been adjusted in the light of first evidence, the resulting posterior probabilities may then be used as priors for subsequent calculation based on new evidence. For example, after two stages of such iteration, 

RABYi,V2) & LGB] yo) (O1 ys) ~ 26] y)ROLYi)er0(6). (5) 

Note, however, that one can argue with equal merit that the posterior probabilities after both data sets y,, y, are available should just be w,(6|y,, v2) « Q(6|y, + y)x,(8). For these formulas to produce different values of +, would be contradictory, i.e., the evidence would support different conclusions depending on the sequence in which it was evaluated. This can be avoided only if 2 has the property 2(6|y, + y.) « L\y)R@ly.). The likelihood function 2 = p(1 — p)"-* indeed has this essential addition property: 

Up|n, + Nz, $, + $2) = pt1 — pymtnd-Gitsd = Lp| m2, $.)R(p|n,, 5:). (6) Since Bayesian formalism is internally consistent, a calculation such as (6) is essentially a check on the validity of the likelihood function; any legitimate & must have the appropriate addition property. 

## Bayesian Analysis of REG Data 

Let us now apply Bayesian formalism to the body of REG data presented in Margins ofReality (Jahn and Dunne, 1987), also published in the Journal for Scientific Exploration (Jahn, Dunne, and Nelson, 1987). From the summary 

26 

Y. H. Dobyns 

table on pp. 352-53 of the book and pp. 30-32 of the Journal article, the “APK” data consist of some 522,450 experimental trials totalling n = 104,490,000 binary Bernoulli events. The Z score of 3.614 is tantamount to an excess of 18,471 hits in the direction of intention. From relation (4), the likelihood function for Bernoulli trials is 2(p|n, s) = p°(1 — p)*-*. The mean of this p distribution is (s + 1)/(m + 2); for large nm its standard deviation is ag= <7 + O(1/n); and it becomes essentially normal. With the values above, 

Q(p|n, s) = p*?263471(] — 52226529. yy, = 0.5001768; o, = 4.89 x 10%. (7) Figure 1 shows this likelihood function for the REG data against a range of p values from 0.4999 to 0.5004. Also shown for comparison is the interval ofp values that are credible under the null hypothesis, calculated as outlined below. 

The REG device itself is constructed to generate groups of Bernoulli trials with an underlying hit probability as close to exactly 0.5 as possible (Nelson, Bradish, and Dobyns, 1989). As part of its internal processing, it compares the random string of positive and negative logic pulses from the noise generator with a sequence of regularly alternating positive and negative pulses generated by a separate circuit. Matches with this alternating “template” are then reported as hits in the final sum. This technique effectively cancels any systematic bias in the raw noise process. While it is conceivable that some bias in the final output could still occur, if for example some part of the apparatus contributed an oscillatory component to the noise that happened to be exactly in phase with the template, or if the counting module should systematically malfunction, such remote possibilities are precluded by a number of internal failsafes and counterchecks incorporated in the circuitry. The device was extensively and regularly calibrated during the period that the Margins data were collected, and from these calibration data it was established that, if p is expressed as 0.5 + 6, then |5| < 0.0002, with no lower bound established. 

Yet further protection against bias is provided by the experimental protocol, wherein each operator generates approximately equal amounts ofdata in three experimental conditions. These are labeled “high,” “low,” and “baseline” in accordance with the operator’s pre-recorded intentions. The “APK” data in Margins are differential combinations of “thigh” and “low” intention data; the combined result is equivalent to inverting the definition of success for the “low” data and computing the deviation of the resulting composite sequence of high and low efforts from chance expectation. Thus, to survive in the APK. results, any residual artifactual bias ofthe device or the data processing would itself have to correlate with the operator’s intention. Specifically, if p, = 0.5 + 61s the probability of an “on” bit, a data set containing a total of N, bits from the high intention and N, bits from the low intention (where the goal is to get “off” bits) will have a null-hypothesis p in the APK of: 

Bayesian REG analysis 

27 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0005-02.png)


**----- Start of picture text -----**<br>
4.0<br>08<br>3 0.6<br>s Null Hypothesis interval<br>Fe 0.4<br>ce<br>0.2 ,<br>a<br>0.5000 0.5001 0.5002 0.5003 0.5004<br>Hit Probabitity P<br>**----- End of picture text -----**<br>


Fig. 1. Likelihood function for PEAR REG data. 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0005-04.png)


**----- Start of picture text -----**<br>
_<br>P= No + NAL = Do) _ N,-<br>M+, 0.5 + 8 (8)<br>**----- End of picture text -----**<br>


Thus, when N, = N,, p, = 0.5, regardless of the value of 6. For the actual Margins data, with N, = 52,530,000 bits and N, = 51,960,000 bits, (VN, — NAN, + N) = 0.0055. Given |5] < 0.0002 as above, the maximum possible artifactual deviation from pA = 0.5 is 1.1 x 10-°. This value is the source of the null hypothesis interval shown in Figure 1. 

While the issue of possible sources ofbias in the REG data could be treated at considerably greater length (see, for a fuller treatment, Nelson et a/., 1989) such discussion is a separate issue from the statistical interpretation of the data. It has been mentioned here only to explain the derivation of the null hypothesis interval. 

Having established the likelihood function (Eq. 7), let us now consider various sets of prior probabilities with which 2 may be combined to arrive at a posterior probability distribution for the value ofp in the actual experiment. First, consider the prior probability corresponding to extreme skepticism. A person who regards any influence of consciousness on the REG output to be impossible a priori should, by the tenets of Bayesian analysis, choose a prior z,(p) = &p — 0.5), where 4(x) is the standard Dirac delta function defined by the property f'bS(x)o(x — x,)dx = f(x,) for anyf and any a, b such that a < x, < b. It then follows that z,(p) will also be a delta function, and after normalizing must in fact be the same function. Since this 

28 

Y. H. Dobyns 

choice of prior probability is clearly impervious to any conceivable evidence, it is illegitimate in any effort to learn from new information, however strongly held on philosophical grounds. 

As an extreme alternative, one might select a prior evincing complete ignorance as to the value ofp, by regarding all the possible values ofp as equally probable: z,(p) = 1 for p € [0, 1] as illustrated in Figure 2a. With this prior the posterior probability x,(p) must, of course, have exactly the same shape as 2. This replicates classical analysis in the following sense: 2 is normal with its center 3.614 standard deviations away from p = 0.5, so, if we define confidence intervals in p centered on the region of maximum posterior probability, we may include as much as 99.97% ofz,(p) before the interval becomes compatible with a point null hypothesis, corresponding to the 3.0 x 10-* p value of a two-tailed classical test. Accounting for the actual spread of the null hypothesis slightly narrows this interval, raising the equivalent p value to 3.3 x 10-4 

It is, however, unnecessary to assume this level of ignorance to arrive at a very similar result. For example, one might regard it as plausible, in light of the measures taken to force p ~ 0.5, that p ought to have some value in a narrow range centered about 0.5 but that within that range there is no strong reason to prefer one p over another. This defines a one-parameter family of “rectangular” priors characterized by their width w: 

1 € lw itw \° 

Figure 2b illustrates the member of this family with w = 10-3. Use of this prior essentially replicates the result from the uniform prior of Figure 2a, since it still includes all ofthe likelihood function except for tiny contributions in the extreme tails. In consequence, w, has the same shape as in the previous 

case for the region 0.5 — $ < p < 0.5 + §, but is uniformly augmented by a multiplicative factor to compensate for the missing tails. Until w is made small enough that 0.5 + | comes within a few standard deviations of the maximum of the effects of this correction remain negligible. Obviously, if the prior is made sufficiently narrow it will become indistinguishable from the null hypothesis interval and the resulting posterior probability can no longer exclude the null hypothesis interval from the region of high likelihood. Figure 3 displays the equivalent p value with which the null hypothesis is excluded for a range of widths of the prior; as above, this p is the conjugate probability to the widest confidence interval about the maximum of 7, that does not include any of the null hypothesis interval. The line labeled “Breakpoint” marks a value of special interest for the width of the prior. For wider priors, the upper limit ofthe confidence range for the Bernoulli pis established by the symmetry condition about the peak, and the condition that the interval not include the null hypothesis range. For narrower priors, this upper limit is dictated by the width of the prior itself. It is unsurprising 

Bayesian REG analysis 

29 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0007-02.png)


**----- Start of picture text -----**<br>
2a: Uniform Prior<br>10 Pros Prooabiity a<br>/\<br>0<br>00.4995 0.5000 0.5005 1<br>Hit Probability P<br>2b: Rectangular Prior, Width = 0.001<br>F5 1500<br>3<br>1000 TT<br>; [~]<br>i \<br>0<br>0.4990 0.4995 0.5000 0.5005 0.5010<br>Hit Probability P<br>Fig. 2. Likelihood and different priors.<br>**----- End of picture text -----**<br>


that this change of regimes is accompanied by an inflection in the p value of the null hypothesis. Beyond the left edge of Figure 3, we should note that when the width of the prior drops to 2.2 x 10-‘, the same as the null hypothesis, the p value of the null rises to 1. This is essentially the same imperviousness previously seen in the delta-fumction prior. Indeed, the family of rectangular priors tends toward a delta function in the limit as the width goes to zero. However, values consistent with the null hypothesis are still excluded at p = 0.05 for w as small as 8.7 x 10-°. Note that this is of the same order as the width of the likelihood function itself. 

Further perspective on the interplay of the evidence with a prior preference for the null hypothesis interval may be obtained by considering another family of priors that specifically favor the null hypothesis to varying degrees but do not have sharp cutoffs of probability. Let x(k, p) = [Qk + LV(k)?Ip*(l — py for any k. All of these functions are properly normalized probability distributions, with mean 0.5 and standard deviation o = 4/(k — 1V/(2k? + 5k + 3), which tends to WEac[for][ large][k.] These[functions][also] become[increasingly] normal for greater k. As in the previous case, they tend to a delta function in the limit k - oo. When one of these functions is used as a prior with 2 from 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0008-00.png)


**----- Start of picture text -----**<br>
30<br>**----- End of picture text -----**<br>



![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0008-01.png)


**----- Start of picture text -----**<br>
Y. H. Dobyns<br>**----- End of picture text -----**<br>



![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0008-02.png)


**----- Start of picture text -----**<br>
ou NS 7 2 ! | a<br>0.00001 0.0001 0.001<br>Width ofRectangularPrior Probability<br>**----- End of picture text -----**<br>


Fig. 3. Conjugate confidence intervals from rectangular priors. 

the Margins data, the resulting x, has mean p, = (s + 1 + A\/(m + 2 + 2k) and standard deviation a, = %\/n + 2k (in the large-n approximation, which is clearly justified), as can be seen from the functional form of 2 and the fact that multiplying by z, is equivalent to the substitution s - s+ kn-n+ 2k, up to normalization. The equivalent Z score, that is, the number of its own standard deviations that separate the peak of the posterior probability distribution from the null hypothesis, becomes Z = (2s — n)/\/n + 2k. While this clearly tends toward zero as k — ©0, it is also clear that large values of k, and hence extremely narrow priors, are needed to change the result appreciably. Figure 4 presents the equivalent p value, as defined for Figure 3, for this family of priors as a function of k. Also shown is the width (standard deviation) of the prior, indicative of how strongly the null hypothesis is favored. Note that to drive the p value above 0.05 (that is, to bring the null hypothesis interval within the 95% confidence interval of the posterior probability) ak > 108, orao < 3 x 10-5, is required. Here the characteristic scale of the prior is actually narrower than that of the likelihood. 

An alternative way of favoring a narrowly defined region of probability often employed in Bayesian analysis, as pointed out by the reviewer of an earlier version ofthis work, is to put some ofthe prior probability in a “lump” at the preferred value. In this case, for example, one might modify any of the priors above by multiplying it by 1 — @ and then adding aé(p — 0.5), for any 0 <a < 1; this inflates the degree of probability accorded the null hypothesis. Large values of a are not very interesting, since a = 1 replicates the completely impervious delta-function distribution. Consider a family ofpriors that might be regarded as plausible by an analyst who believes the null hypothesis has 

Bayesian REG analysis 

31 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0009-02.png)


**----- Start of picture text -----**<br>
0.1 ——<br>> sigmaof Poe |<br>a i i<br>te !<br>1e4 1e5 1e6 1e7 1e8<br>K value<br>Fig. 4. Conjugate probabilities from K-family of priors.<br>**----- End of picture text -----**<br>


considerable support but who has no reason to prefer one value of p over another within some reasonable range for the alternate. This might be represented as z,(a, w, p) = ai(p — 0.5) + (1 — a)x,(p), where z,(p) is the same “rectangular” prior defined as 7,(w, p) in Eq. 9. Thus =,(a, w, p) is a twoparameter family of priors in a, the extra weight initially assigned to the null hypothesis, and w, the range ofplausible alternatives. The confidence-interval formulation discussed above is somewhat awkward for the posterior probability resulting from these functions, since they are highly bimodal. However, this bimodality arises from the preservation of the delta-function component and also suggests that the posterior probability of the null hypothesis, given this prior, may be computed from the strength of the delta-function null in the (normalized) posterior probability +,. The contribution from the part of the x,, component compatible with the null hypothesis is negligible for most values of a and w. 

The upper portion of Figure 5 presents a contour plot of the posterior probability ofp = 0.5 for a range ofa and w values. Both scales are logarithmic, with grid lines shown at 1, 3, 5, 7, and 9 times even powers of 10. For a values as large as 0.9, the posterior probability of the null is less than 0.05 for w = 5 x 10+. As a grows the calculation becomes less sensitive to w and less responsive to the data, as expected. 

The lower portion of Figure 5 shows a related quantity of interest, the relative strength ofthe null hypothesis in the prior and posterior distributions as given by the coefficient of the delta-function component. This can be regarded as the degree to which the null hypothesis component is amplified by the evidence. Two noteworthy features are that for small a values this 

32 

Y. H. Dobyns 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0010-02.png)


**----- Start of picture text -----**<br>
00 Posterior Probability of Null Component<br>~ TR SORSST<br>| L Lis i [~ SS a : —<br>ZS SCNT<br>2 0.10 ff IC IN IY UNUING N ON NG<br>== WAeSee ee<br>2 ep fA NA TNT AN ONT NT<br>0.01 1e4 0.001 0.01 0.10 1.00<br>Width of Rectangular Component<br>+00 Amplification of Null Component<br>_ OSS SE =<br>wwF5® «=o + Cot£1SSLSON ROE|WRK SN A Wl SOONSeeeS WORE NR OF anae Ale<br>5 | |<br>Ss<br>: ae IE ap<br>0.01 1e-4 = 0.001 0.01 0.10 1.00<br>Width of Rectangular Component<br>Fig. 5.<br>**----- End of picture text -----**<br>


amplification factor tends toward a constant depending only on w, and that even for a ~ 0.85, the null hypothesis emerges twenty times less likely after accounting for the evidence for w= 5 x 10-4, 

In summary, an examination of various possible prior probability distributions leads to conclusions ranging from confirmation of the classical odds against the null hypothesis to confirmation of the null hypothesis, depending on one’s choice of prior. Priors that lead to confirmation, or low odds against, the null hypothesis, are associated with large concentrations of probability on 

Bayesian REG analysis 

33 

the null hypothesis, or ranges around the null that are narrow compared to the likelihood function. In other words, they must be relatively impervious to evidence. 

For all of these examples, the evidence (as manifested in the likelihood function) has remained constant. The variability of the conclusions has resulted entirely from the various choices of prior probability distribution. With the pure delta-function prior standing as a cautionary example ofa prior belief that cannot be shaken by any evidence whatsoever, it seems suggestive that those priors which lead to conclusions most strongly in disagreement with the classical analysis are precisely those which most nearly approach the deltafunction. A possibly oversimplified summation is that the likelihood function, taken alone, would lead to the same conclusion as a classical analysis, while the more an analyst wishes to favor the null hypothesis a priori, the more the posterior conclusions will likewise favor the null. This at least suggests that a prior hypothesis leading to strong disagreement with classical analysis may be inappropriate to a given problem. 

Concerns of appropriate choices of prior hypotheses will be addressed further below, in light of another method of analysis. 

## Bayesian Hypothesis Testing and Lindley’s Paradox 

The last example in the previous section was chosen in part because it leads rather directly to the question of using Bayesian analysis to compare two distinct hypotheses, rather than evaluating a parameter range undera single hypothesis. Consider for example the hypotheses 2,(6) and ,(6), where =, now denotes an alternative prior. Let p) and p, denote prior probabilities on the hypotheses, with p, + p, = 1 so that the two hypotheses comprise exhaustive alternatives. The relative likelihood of the hypotheses can also be stated as the prior odds Q = p)/p,. 

Given the two hypotheses and their respective prior probabilities, an overall prior probability distribution for @ can be constructed (6) = Dox,(0) + pi7,(6). This may then be used in a Bayesian calculation resulting in a posterior probability +’(6) = L@|y)r(6), where L(6|y) = &@ly)/i@ 2(6| y)r(0)d6 is the normalized likelihood. This posterior probability can unambiguously be di-' vided into components arising from the two hypotheses, a’ = 24 + xj, such that 

a(Oly = LO|y)poro(6) and «(6|y) = L@|y)p,2,(6). (10) The posterior probabilities for the two hypotheses are clearly the total integrals of their respective contributions to the overall posterior probability: pj = { 6 xe y)d6 and likewise for p}. Thus the posterior odds are 

34 

Y. H. Dobyns 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0012-02.png)


**----- Start of picture text -----**<br>
, f LO Y)Powo(8)db<br>0'(6|y) Do @<br> =mT.<br>f L(O\y)pix,(0)d0<br>f £(6| y)x0(6)d0<br>=| |? (11)<br>f 281 y)ar,()d0 f<br>= BO)<br>**----- End of picture text -----**<br>


where L(6|y) « 2(6]y) has been used to eliminate the explicit normalizing constant. The last two lines of Eq. 11 define the Bayesian odds adjustment factor, or odds ratio, B(y). Note that, unlike 2(6|y), By) is not completely objective, since prior probability distributions are required to calculate it. Applications of this formula are referred to as Bayesian hypothesis testing, as distinct from the Bayesian parameter evaluation described in previous sections. 

. 

In the general context of Bayesian hypothesis testing there can arise an oddity in the statistical inference between the two alternatives. When a point or very narrow null hypothesis x, is being tested against a diffuse or vaguely characterized alternative hypothesis 7, Bayesian hypothesis testing may lead to an unreasonable result in which data internally quite distinct from the null hypothesis are nevertheless regarded as supporting the null in preference to the alternate. Mathematically, a likelihood 2 whose maximum is several standard deviations away from the null still yields B(y) > 1. This situation is referred to by various authors as Jeffreys’ paradox or Lindley’s paradox. It is well described by G. Shafer (1982): 

“Lindley’s paradox is evidently of great generality; the effect it exhibits can arise whenever the prior density under an alternative hypothesis is very diffuse relative to the power of discrimination of the observations. The effect can be thought of as an example of conflicting evidence: the statistical evidence points strongly to a certain relatively small set of parameter values, but the diffuse prior density proclaims great skepticism (presumably based on prior evidence) towards this set of parameter values. If the prior density is sufficiently diffuse, then this skepticism will overwhelm the contrary evidence of the observations. “The paradoxical aspect of the matter is that the diffuse density x,(0) seems to be skeptical about all small sets of parameter values. Because of this, we are somewhat uneasy when its skepticism about values near the ‘observed interval’ overwhelms the more straightforward statistical evidence in favor of those values. We are especially uneasy if the diffuseness of z,(@) represents weak evidence, approximating total ignorance; the more ignorant we are the more diffuse 7,(6) is, yet this increasing diffuseness is being interpreted as increasingly strong evidence against the ‘observed interval.’” 

— 

Shafer’s article then proceeds to a cogent argument that cases where a Lindley paradox occurs are precisely those where ordinary Bayesian hypoth- 

Bayesian REG analysis 

35 

esis testing is misleading and should not be used. (In fairness, one should note that the major development of Shafer’s treatment is an extension ofBayesian formalism to deal with this awkward case; and that the published article includes an assortment ofcounter-arguments from various authors.) The problem, of course, is that a diffuse prior is being treated as evidence against the hypothesis in question. As noted above, B(y) is not an objective adjustment of subjective prior odds between hypotheses, but depends on a second subjective choice of prior distribution for an alternate. (If the null hypothesis is also not well defined, it presents yet a third opportunity for subjective contributions.) If not carefully noted, these further subjective elements can be quite as inexplicit and misleading as those that Bayesians object to in classical analvsis. 

A further practical difficulty with hypothesis testing, relative to classical treatments, is that the null hypothesis is always compared to a specific alternative. In many situations, including the PEAR experiments, investigators are interested in any possible deviation from a specified range of possibilities, without having enough information about the possible character of such a deviation to construct one specific alternate with any degree of conviction. A diffuse alternative that encompasses a wide range of probabilities is not a satisfactory option. This can be seen abstractly, from consideration of the Lindley paradox in cases where the statistical resolving power of a proposed experiment will be very high; it can also be argued on other grounds, as will be discussed below under the heading of statistical power. 

## Hypothesis Testing on PEAR Data 

The extreme sharpness of the likelihood function for the PEAR data base used earlier makes any hypothesis test on it susceptible to a Lindley paradox. Unless the prior for the alternate is also narrowly focused in the region of high likelihood, B(y) will claim unreasonable support for the null hypothesis. One might then argue that the recipe for avoiding dubious results is to employ a narrow range of values for the alternate hypothesis. There are, after all, numerous arguments that anomalous effects such as PEAR examines should be small. Perhaps the simplest argument is that if such effects were large, they would not be a subject of dispute! Despite such reasoning, as recently as 1990 an article appeared using, at one point, z,(p) = 1, p € [0, 1] for the alternate in a hypothesis test (Jeffreys 1990). The use of highly diffuse priors can thus be seen to be a real and current practice meriting cautious examination, rather than a purely argumentative point. 

The final section of the parameter-evaluation discussion above, with its two-component prior, is already very close to a hypothesis test. The only major difference is that the weighting parameter a is absorbed into the odds 2, leaving a one-parameter family of alternate priors for comparison with the null. Figure 6 shows the value ofB for a range w values (where w is the width of the rectangular alternate). The solid line, marked “Symmetric”, can be 

36 

Y. H. Dobyns 


![](/Users/roberttaylor/Documents/woo/woograph/sources/pear-1992-bayesian-analysis-reg-data/images/1992-bayesian-analysis-reg-data.pdf-0014-02.png)


**----- Start of picture text -----**<br>
Odds adjustment for point null versus rectangular alternate<br>Orr<br>_———————————ee$aa ry<br>a A A”<br>a es nn<br>oe<br>=. OHOHOHOHEOmmdox.x."”..*OQ@nD}PB0FBDma—aO Dee eee |<br>4 Oe TNO COU” AS(<br>2<br>eS Te<br>AA ca”NR A SR<br>0 eee<nee<br>||<br>SO20 |<br>aa ye<br>10-4 0.001 0.01 0.10 1.0<br>. Width of rectangular alternate<br>Fig. 6.<br>**----- End of picture text -----**<br>


seen to be the limit of the w-dependence shown in Figure 5 for a > 0. The dotted line, marked “One-Tailed”, shows the odds ratio for the null against a one-sided version of the rectangular prior, which has support only for p > 0.5. Since the PEAR results are based on a directed hypothesis, one-tailed statistics are appropriate in a classical framework, and this would seem to be an appropriate Bayesian analog, as well. Both functions attain a minimum at w= 48 x 10-4, for B = 0.00316 in the one-tailed case. 

## Inflation of p-values and Statistical Power 

The smallest B factor in the hypothesis comparison above was a factor of 10 larger than the two-tailed p-value of 3 x 10-* quoted in Margins. The smallest B to emerge from a direct hypothesis test for these data is 0.00146, for comparison of a point null against a point alternate located exactly at the maximum likelihood p = s/n. This is still a factor of 10 larger than the corresponding one-tailed value (the Bayesian test is also “one-tailed” in this case). The tendency ofhypothesis comparison to emerge with a larger B value than the corresponding p-value of a classical test is often cited by Bayesian analysts as evidence that classical p values are misleading for large databases, and should be adjusted by some correction factor, perhaps of order n’. (See, for example, the discussions by Good and Hill in the latter portions of the Shafer article; see also Jeffreys (1990).) Such proposals generally fail to take 

- Bayesian REG analysis 

37 

into account considerations of statistical power, a somewhat neglected branch of analysis. 

Conventional statistical reasoning recognizes two types of errors. The more commonly acknowledged Type I or @ error is the false rejection of the null hypothesis, where a is the probability of making such an error. Type II or 8 error is the false acceptance of the null hypothesis, with 6 likewise being the probability of making the error. 1 — 8 is usually called the statistical power of a test. In any real situation, the null hypothesis is either true or false and therefore only one of the two types of error is actually possible. A less obvious point is made in the literature: 

“The null hypothesis, of course, is usually adopted only for statistical purposes by researchers who believe it to be false and expect to reject it. We therefore often have the curious situation ofresearchers who assume that the probability oferror that applies to their research is 6 (that is, they assume the null hypothesis is false), yet permit 8 to be so high that they have more chance of being wrong than right when they interpret the statistical significance oftheir results. While such behavior is not altogether rational, it is perhaps understandable given the minuscule emphasis placed on Type II error and statistical power in the teaching and practice of statistical analysis and design . . .” (Lindsey 1990) 

Consider an experiment involving N Bernoulli trials where one wishes to know whether they are evenly balanced (p = 0.5, the null hypothesis) or biased, even by extremely small deviations from the null hypothesis. (This is in fact the case in PEAR REG experiments.) Consider two cases: the null hypothesis is true (p = 0.5000); the null hypothesis is false with p = 0.5002. Assume that the experiment (in each case) is analyzed by two statisticians, neither of whom has any advance knowledge ofp: a classical statistician who rejects the null hypothesis if a two-tailed p-value < 0.01 is attained, and a Bayesian who, using a uniform prior for the alternate, regards the experiment as supporting the null hypothesis if the odds adjustment factor B > 1, and as supporting the alternate if B < 1. To give the probability estimates some concrete reality we may imagine the experiment being run many times with different pairs of analysts. The probability that the classical statistician makes a type I error is defined by the choice of a, and is independent of N. The table below gives the probability, for various N, of a type I error by the Bayesian analyst (regarding the evidence as favoring the alternate when the null is true) and the probability of type II error by either analyst. For either a true null or a true alternate, the final experimental scores follow a binomial distribution with N determined by the row ofthe table and p = .5000 or .5002 respectively. For both the classical analyst and the Bayesian analyst, one may calculate the number of successes needed for an analyst to reject the null hypothesis g, where the Bayesian is regarded as rejecting the null if B < 1. The table then quotes the error frequencies that follow from the actual sucess distributions under each hypothesis and the analytical criterion used for rejection. The 

38 

## Y. H. Dobyns 

TABLE I 

Error rates under different analyses 

|N|||Null is true|Null is false|Null is false|
|---|---|---|---|---|---|
||||@ error, Bayesian|8 error, classical|8 error, Bayesian|
|100<br>10,000|||0.028<br>0.0031|0.995<br>0.994|0.982<br>0.998|
|10<br>10°<br>10*|||2.6 x 10~<br>7.6 x 10-8<br>2.2 x 10-5|0.985<br>0.905<br>0.077|0.999<br>0.906<br>0.595|
|1.5|x|108|1.86 x 10-3|0.010|0.267|
|10°|||6.8x10-6|3.6x10-*|1.8x10%|



probabilities of type II error combine the probability of erroneous acceptance of the null hypothesis with that of (correct) rejection of the null due to mistakenly inferring p < 1/2. For the considerations of columns 3 and 4, p > 1/ 2, and both conclusions are equally erroneous. The abrupt drop of 6 values in the last few lines of the table may seem jarring, but is a rather generic feature of power analysis. For any given constant effect size, there will be a fairly narrow range of N (as measured on a logarithmic scale) for which any specific test will quickly shift from being almost useless to being virtually certain to spot the effect. 

A salient feature is that the Bayesian calculation, with this prior, starts out more vulnerable to type I error, and less vulnerable to type II error, for small N: however, they are both so likely to suffer type II error that this is not very interesting. For large N, the Bayesian calculation is uniformly more conservative in that its probability of falsely rejecting the null hypothesis declines with N, while the classical analysis uses a constant p-value criterion for rejecting the null. Correspondingly, the Bayesian calculation has a far higher likelihood than the classical of falsely accepting the null hypothesis. The row for N = 1.5 x 108 is of special interest, because for this value the classical analysis attains equal likelihood of type I and type I errors. At this level the Bayesian analysis still has over 1 chance in 4 of incorrectly confirming p = 0.5. 

Table I actually makes an extremely generous interpretation ofthe Bayesian output. The Bayesian analyst is assumed to regard the data as supporting the alternate hypothesis as soon as the Bayes factor B < 1. However, as mentioned above, various authors write as though the odds adjustment factor B ought to be regarded as an analogue to the p-value for a data set. Had this sort of reasoning been used in constructing Table I, the Bayesian analyst would still have p = 0.634 for committing a type II error on 150 million trials. The Bayesian analysis used is not optimized for the problem oftesting, say, a circuit that produces “on” signals with a probability that is definitely either p = 0.5 or p = 0.5002. Neither is the classical analysis. If the problem were to distinguish these two discrete alternatives, a Bayesian test would compare two point hypotheses; while a classical test might, with given reliability levels, 

Bayesian REG analysis 

39 

establish ranges of output for which a circuit would be classed as “definitely 0.5”, “definitely 0.5002”, or “inconclusive, further testing required.’ The actual problem may be envisioned as a sociological thought experiment in which large numbers of Bayesian and classical analysts are presented only with the output of the device, and the information that the underlying Bernoulli probability either was or was not 0.5. The uniform Bayesian alternate simply represents ignorance ofpossible alternative values ofp , and is directly analogous to the situation, described earlier, for selection of priors in anomalies data. The second to last line ofTable I says that, were such an experiment conducted and each analyst presented with 150 million trials with either p = 0.5 or p = 0.5002, the classical analysts would produce 1% false positives and 1% false negatives; while the Bayesian analysts would produce a vanishingly tiny fraction of false positive reports but over 26% false negatives—deviant datasets identified as unbiased. 

In a more general vein, for large databases with small effects, it is apparent in light of the various discussions above that any Bayesian hypothesis comparison will yield an odds adjustment factor larger than the classical p-value for the same data. If the odds adjustment B is regarded as equivalent to a p- value, or a corrected version of it, the inevitable consequence will be a test less powerful than the classical version, and so more prone to missing actual effects that may be present for any given database size. 

An important consideration in statistical power analysis is the effect size. One seldom has the advantage of knowing in advance the magnitude of potential effects. In the anomalies research program at PEAR, for example, any unambiguous deviation from the demonstrable null hypothesis range has profound theoretical and philosophical import. While traditional power analysis would suggest scaling the sample sizes to the smallest effect clearly distinguishable from the null hypothesis range, this would be totally impractical in that it would require datasets several orders of magnitude larger than those published in Margins. This, too, is a standard situation frequently encountered in power analysis, in that effects of potential interest may nonetheless be too small to identify in studies of manageable size. While in fact the apparent effect size manifest in the PEAR data is much larger than this pessimistic case, there was no way of[knowing][ in][advance][ that][ this][would][be][ so.][ Confronted] with the possibility of very small effects, the only viable alternative may be to conduct such measurements as are feasible, with the awareness that effects may be too small to measure in the current study; in which case the experiment will at least permit the establishment of an upper bound to the effect in question. 

In such a situation, a Bayesian analysis using the uniform alternate prior is obviously too obtuse to be of value; it retains a high chance of a false negative report for dataset sizes where the classical test has a high degree of reliability. At the same time, information about plausible alternates may well be so scant that the uniform prior, or an only slightly narrower one, is nonetheless a fair summary of one’s prior state of knowledge. Under these circum- 

40 

Y. H. Dobyns 

stances, the reasonable course would seem to be adoption ofclassical statistical tests with an experiment designed to exclude any procedures, such as optional stopping, which would invalidate the tests. The next section will discuss optional stopping and related issues in more detail. 

## Relative Merits: Bayesian vs. Classical Statistics 

Bayesian analysis is occasionally claimed to remedy various shortfalls in the classical analysis of very large data bases (Jeffreys, 1990; see also Utts, 1988). Beyond the question of replacing classical p values with Bayesian odds adjustment factors discussed above, two other sources of inadequacy are usually cited: First, any repeated measurement eventually reaches a point of diminishing returns where further samples only refine measurement of systematic biases rather than of the phenomenon under investigation. Second, indefinite continuation of data collection guarantees that arbitrarily large excursions will eventually arise from statistical fluctuations (“sampling to a foregone conclusion”). Both of these concerns, together with the notion that Bayesian analysis is specially qualified to deal with them in a way that classical analysis is not, are not substantiated by well-designed REG experiments in general, or by the Margins data in particular. 

1. The inevitable dominance of bias. The maximum possible influence of biasing effects in this experiment has been discussed in the context of the “null hypothesis interval” above, and displayed graphically in Fig 1. In an experiment that contrasts conditions where the only salient distinction is the operator’s stated intention, any systematic technical error must itself correlate with intention to affect the final results. While unforseen effects may never be completely ruled out, it would require considerable ingenuity to devise an error mechanism that achieved this correlation without itselfbeing as anomalous as the putative effect. Over the eight years of experimentation that went into the Margins database (twelve years as of this writing), both the PEAR staff and interested 

’ outsiders, including prominent members ofthe critical community, have been unable to find any such mundane source ofsystematic error. Beyond this, the bias question in REG data is an improper conflation of two unrelated issues. As pointed out by Hansel (1966) in the evaluation of any data, a statistical figure-of-improbability measures only the likelihood that data are the result of random fluctuation. It remains for each analyst to draw conclusions as to whether the deviation from expected behavior is more plausibly due to the effect under investigation or to an unaccounted-for systematic bias in the experiment. Thus, the question of bias is essentially external to the purely statistical issue of whether or not the data, are consistent with a null hypothesis. 

2. Arbitrarily large excursions. The conclusion of Feller’s (1957) discussion of the law of the iterated logarithm may be summarized thus: Any 

Bayesian REG analysis 

41 

threshold condition for the terminal Z score of a binary random walk that grows more slowly than \/2/og(/og(n)) will be exceeded infinitely many times as the walk is indefinitely prolonged, and thus is guaranteed to be exceeded for arbitrarily large data bases. Obviously, this is of concern only for experimental sequences ofindeterminate length, where one could, in principle, wait for one of these large excursions to occur, and then declare an end to data collection. Any experiment ofpredefined length will always have a well-defined terminal probability distribution. Without exception, all PEAR laboratory data, including the Margins array, have conformed to the latter, specified series length protocols. Nevertheless, if the Margins data are arbitrarily subjected to a worstcase, “optional-stopping-after-any-trial” analysis, the probability that a terminal Z score of 3.014 could be attained at any time in the program’s history computes to <0.007. Under the somewhat more realistic assumption that data accumulation could be halted only after any of the 87 series that comprise the database, the terminal probability becomes =0.002. The actual history of the experimental program clearly demonstrates that no optional stopping strategy can have been applied to publication decisions, for significant effects have steadily been apparent from the collection of the first series onward (Dunne, Jahn, and Nelson, 1981), and the various publication points have never coincided with local maxima in the accumulating results (Jahn 1982; Dunne, Jahn, and Nelson 1982; Jahn, Dunne, and Nelson 1983; Nelson, Dunne, and Jahn 1984; Nelson, Jahn, and Dunne 1986; Jahn and Dunne 1986; Jahn 1987). For classical tail-measurement statistics to be legitimate, it is sufficient that the termination condition be independent of the outcome of the experiment (Good 1982). 

3. Special competence of Bayesian analysis. The likelihood function of Bayesian analysis will as a rule replicate the results ofa classical analysis in the sense that, if classical statistics compute a Z score z, then the likelihood function will have a mean that is z of its own standard deviations away from a point null hypothesis. (This follows from the functional form of 2.) Any differences in interpretation must therefore come from the use of different priors. We have seen above that Bayesian parameter evaluation with a prior that is uniform in the region of high likelihood likewise replicates the classical analysis, since this creates a posterior probability with the same shape as the likelihood. While nonuniform priors can change this conclusion, for a likelihood function as sharply focused as that of the Margins data such priors must be close to the null-hypothesis delta function, i.e., recalcitrant almost to the point of impenetrability, before they force acceptance of the null hypothesis. Direct comparison of competing hypotheses, on the other hand, is vulnerable to confounds from inappropriate alternate priors . 

As already noted, no analysis, Bayesian or otherwise, will guard indefinitely 

against an unforseen bias. Table I and the related discussion showed that 

42 

## Y. H. Dobyns 

Bayesian analysis with a recalcitrant prior eventually agrees with classical analysis in rejecting the null hypothesis, when enough data are accumulated with a constant mean shift. They also show an example, appropriate to the class of REG-type experiments, where Bayesian analyses that choose priors to be very conservative are also necessarily very insensitive and must suffer a large probability of type II error. This is true whether the effect is real or a systematic error, and the mode of analysis grants no special ability to distinguish the two cases. 

## Data Scaling 

A final point ofcomparison concerns the interpretation of the Margins data on various scales. Classical analysis does not require that any special attention be paid to the intermediate structure of the experimental data; if a Z score is computed for each series, and the assorted series Z scores are compounded appropriately, the composite result is exactly the Z that would result were the data treated in aggregate. This occurs because, no matter what scale is used to define elements of the data, the increased consistency of the results exactly compensates for the loss of statistical leverage from the decreased N of units. Processing REG data in large blocks is essentially a signal averaging procedure, unusual only in that it is performed algorithmically on stored data rather than in preprocessing instrumentation. 

Directly checking for the same sensible scaling property in Bayesian analysis would entail developing an extension of the formalism for continuously distributed variables, beyond the scope of this discussion. However, a cursory look at the issue can be accomplished by examining the series data breakdown in Margins. The column listing p < 0.5 allows the 87 series to be regarded as 87 Bernoulli trials, each one returning a binary answer to the question, “Did the operator achieve in the direction ofintent, or not?’ Naturally a great deal of information is lost in this representation, since the differential degree of success or failure cannot be reckoned, but it remains instructive. Of the 87 series, 56 were “successes” as Bernoulli trials. The binomial distribution for 87 p = 0.5 trials has p = 43.5, o = 4.66. The actual success rate thus translates to z = 2.68, p = 0.004 one-tailed. The loss of information is seen in the reduction of significance, but the result is consistent in being a strong rejection of the null. 

Not so for a Bayesian hypothesis test against the uninformed alternate =, = 1. For the binary data, as we saw, B = 12; but B(87, 56) = 0.2. Where the reduced information decreased the significance of the classical result, as one might expect, it has inverted the Bayesian result from a modest confirmation of the null to a modest rejection of the null. The discrepancy, of course, lies in the Lindley paradox: the naive alternate prior is inappropriate for the binary test, but not unreasonable for the vastly larger effect that must be present, if the effect is real on the series scale. The fact that the inversion occurs is itself confirmatory evidence for the reality of the mean shift and therefore evidence 

Bayesian REG analysis 

43 

against the utility of a test that regards the data as supporting the null hypothesis. 

## Final Comments and Summary 

The main points to emerge from this study are: 

1. For a Bayesian analysis of Bernoulli trials an objective likelihood function can be constructed which obeys the necessary addition rule for consistent handling of accumulating data (Eq 6). The likelihood function has the same distribution as a classical estimate of confidence intervals on the value of p , and differences of interpretation can therefore arise only from the choice of priors. 

2. It therefore follows that a prior that is uniform in the region of high likelihood, thus producing a posterior probability of the same shape as the likelihood, replicates the classical analysis. For the PEAR data, this reproduces a two-tailed p of 3.0 x 10-4 against a point null hypothesis. 

3. Prior belief favoring the null hypothesis impacts the conclusions. In its ultimate expression, where only values consistent with the null hypothesis are allowed prior support, no evidence can sway the outcome. Less extreme forms continue to reject the null hypothesis (exclude it from reasonable parameter confidence intervals) unless the prior includes much ofthe probability within the null (thus approaching the impervious case) or is narrower than the likelihood (and therefore narrower than the statistical leverage of the known number of trials justifies.) Some examples using the PEAR database include: Exclusion of the null hypothesis from at least the 95% posterior confidence interval for a normal prior centered on the null hypothesis with o as small as 3 x 10-5, compared to o = 4.9 x 10-5 for the likelihood function; posterior odds against the null hypothesis of 20 to 1 for a prior that starts with 85% of the strength concentrated at p = 0.5 and the remainder uniformly distributed with width 5 x 10-‘. 

4. Hypothesis comparison needs to be approached with caution because the odds adjustment factor B(y) contains a contribution from the choice of prior probability distributions, and so is at least as vulnerable to prior prejudices as are the prior odds Q (Eq. 9) 

5. Hypothesis tests return odds correction factors larger than classical p- values even when near-optimal cases are chosen. For the PEAR data, the optimal case is a comparison ofa point null against a point alternate at p = 0.50018 (the maximum of the likelihood function), leading to B = 0.00146 (odds of 685 to 1 against the null.) A consideration of statistical power, however, demonstrates that this does not establish a flaw in, or correction to, classical p-values but is a simple consequence of adopting a less sensitive test. 

6. Examination of the response of Bayesian hypothesis testing to large 

## 44 

## Y. H. Dobyns 

databases indicates that claims of special ability to deal with biases or optional stopping, or of qualitatively superior response to increasing amounts of data, compared to classical statistics, are unwarranted. 

7. In a situation such as confronted by the PEAR program and related investigations, where any detectable effect is offundamental interest and importance, the necessity of having a specific alternate hypothesisfor a Bayesian hypothesis test is a limiting and potentially confounding factor. A prior that is diffuse enough to reflect ignorance of potential effects will have much less statistical power than an appropriate classical test. 

Thus, while Bayesian statistical approaches have the virtue ofmaking their practitioner’s prejudices explicit, they may in some applications allow those prejudices more free rein than is usually acknowledged or desirable. Whereas a classical analysis returns results that depend only on the experimental design, Bayesian results range from confirmation of the classical analysis to complete refutation, depending on the choice ofprior. Those priors that disagree strongly with the classical analysis frequently show one or more suspect features, such as being either very diffuse or pathologically concentrated with respect to the likelihood. (While it violates the definition ofa prior to adjust it with respect to an observed effect, the width of the likelihood is determined only by the experiment’s size, not its outcome, and is therefore a legitimate guide to the characteristics of reasonable priors.) This would suggest that, the more strongly a Bayesian analysis disagrees with a classical result, the more likely the disagreement is due to a subjective contribution of the analyst. Given the impact of prior probabilities, one might argue that the proper role of a Bayesian analysis should be strictly to quote likelihood functions and allow each reader to impose his own priors. However, the philosophical exercise of justifying (or refuting) various priors remains a valuable one, particularly for clarifying the meaning of a particular result. 

## Acknowledgements 

The author wishes to thank Robert Jahn, Brenda Dunne, Roger Nelson and Elissa Hoeger for reading earlier drafts of the manuscript and providing valuable advice. The Engineering Anomalies Research program is supported by major grants from the McDonnell Foundation, the Fetzer Institute, and Laurance S. Rockefeller. 

Correspondence and requests for reprints should be addressed to York Dobyns, Princeton Engineering Anomalies Research, C-131 Engineering Quadrangle, Princeton University, Princeton, New Jersey 08544-5263. 

## References 

- Dunne, B. J., Jahn, R. G., & Nelson, R. D. (1981). An REG Experiment with Large Data-Base Capability. Princeton University: PEAR Technical Note. 

- Dunne, B. J., Jahn, R. G., & Nelson, R. D. (1982). An REG Experiment with Large Data Base 

Bayesian REG analysis 

45 

Capability, II: Effects of Sample Size and Various Operators. Princeton University: PEAR Technical Note. 

Feller, W. (1957). An Introduction to Probability Theory and Its Applications. Volume 2. (2nd ed.) New York, London: John Wiley & Sons. Good, I. J. (1982). Comment [on Shafer (1982), see below]. Journal ofthe American Statistical Association, 77, 342. Hansel, C.E. M. (1966). ESP /A Scientific Evaluation. New York: Charles Scribner’s Sons. Jahn, R.G. (1982). The persistent paradox of psychic phenomena: An engineering perspective. Proceedings ofthe IEEE, 70, 136-170. Jahn, R. G. (1987). Psychic Phenomena. In G. Adelman, Ed., Encyclopedia of Neuroscience, Vol. IT. pp. 993-996. Boston, Basel, Stuttgart: Birkhauser. Jahn, R. G., & Dunne, B.J. (1986). On the quantum mechanics ofconsciousness, with application to anomalous phenomena. Foundations of Physics, 16(8) 721-772. Jahn, R. G., & Dunne, B. J. (1987). Margins ofReality. San Diego, New York, London: Harcourt Brace Jovanovich. 

Jahn, R. G., Dunne, B. J., & Nelson, R. D. (1983). Princeton Engineering Anomalies Research. In C. B. Scott Jones, Ed., Proceedings of a Symposium on Applications ofAnomalous Phenomena, Leesburg, VA., November 30-December 1, 1983. Alexandria, Santa Barbara: Kaman Tempo, A Division of Kaman Sciences Corporation. Jahn, R. G., Dunne, B. J., & Nelson, R. D. (1987). Engineering Anomalies Research. Journal of Scientific Exploration, 1(1), 21-50. Jeffreys, W. H. (1990). Bayesian Analysis ofRandom Event Generator Data. Journal ofScientific Exploration, 42), 153-169. Lipsey, M. W. (1990). Design Sensitivity: Statistical Power for Experimental Research. Newbury Park, London, New Delhi: SAGE Publications. Nelson, R. D., Bradish, G. J., & Dobyns, Y. H. (1989). Random Event Generator Qualification, Calibration, and Analysis. Princeton University: PEAR Technical Note. Nelson, R. D., Dunne, B. J., & Jahn, R.G. (1984). An REG Experiment With Large Data Base Capability, III: Operator Related Anomalies. Princeton University: PEAR Technical Note. Nelson, R. D., Jahn, R. G., & Dunne, B. J. (1986). Operator-related anomalies in physical systems and information processes. Journal of the Society for Psychical Research. $3(803) 261-286. Shafer, G. (1982). Lindley’s Paradox. Journal ofthe American Statistical Association, 77, 325351. Utts, J. (1988). Successful replication versus statistical significance. Journal ofParapsychology, $2, 305-320. 

