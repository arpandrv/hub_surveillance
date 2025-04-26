# Sample Size Calculation for Mango Pest Surveillance in Northern Australia

## Introduction

Early detection of mango pests and diseases is critical for Northern Australian growers to prevent severe outbreaks. A web-based tool can guide growers on how many mango plants to inspect (sample) to be confident of catching a problem if it exists. The required sample size depends on statistical parameters and field conditions: the total number of plants (population size N), the desired confidence level (which determines the z-score), the precision or margin of error (d, set to 5%), and the expected prevalence of pest/disease (p). Below, we outline the sample size formula and its implementation, and provide realistic seasonal prevalence assumptions for mango pests in Northern Australia. We also discuss how environmental factors (temperature, humidity, rainfall) influence pest prevalence, and how changes in p, N, or confidence (z) affect the required sample size n.

## Sample Size Formula for Surveillance

To determine the number of plants to survey, we use a sample size formula for proportions. This formula ensures that with a given confidence level, the sample proportion will be within the specified precision (±5%) of the true infestation rate. For a very large population (essentially infinite), the required sample size m is:

m = (z² p(1−p))/d²

where z is the z-score corresponding to the chosen confidence level (e.g. 1.645 for 90%, 1.96 for 95%, 2.575 for 99%), p is the expected prevalence (proportion of plants infested or diseased), and d is the margin of error (here 0.05). In our context, p represents the assumed proportion of mango plants that would show signs of the pest/disease if it is present under the given conditions.

Since growers will input the finite number of plants N on their property, we apply a finite population correction to avoid overestimating the needed sample. The adjusted sample size n for a finite population is given by:

n = m/(1+(m-1)/N)

where m is the infinite-population sample size from the first formula. This can be expanded and written as:

n = (N z² p(1-p))/(d²(N-1) + z² p(1-p))

Using this formula, the tool can compute how many plants n need to be surveyed to achieve the desired confidence. For example, if a grower has a very large orchard, the formula approaches n ≈ z²p(1-p)/d². If the orchard is smaller, the fraction reduces the required sample. This formula is standard for estimating population proportions with a specified confidence and precision. After computing n, it should be rounded up to the next whole plant (since we can't inspect a fraction of a plant) to ensure the desired confidence level is met.

## Seasonal Pest Prevalence Assumptions

Expected pest/disease prevalence (p) in mango orchards can vary greatly with the season in Northern Australia's tropical climate. We have the wet season, the dry season, and the flowering period (which typically occurs during the dry season) to consider. Based on agricultural research and typical observations, we can assign realistic baseline values of p for each period. Table 1 below summarizes typical prevalence (p) values by season for mango pests and diseases in Northern Australia:

| Season | Typical Pest/Disease Prevalence (p) |
|--------|-----------------------------------|
| Wet Season (hot, rainy) | ~0.10 (10%) |
| Dry Season (cool, arid) | ~0.02 (2%) |

**Wet Season (e.g. November–April):** The monsoonal wet season brings high humidity, warm temperatures, and frequent rainfall. Pests and diseases flourish under these conditions. For instance, the fungal disease anthracnose can infect an extremely high proportion of mango fruits during a rainy season – studies report >90% incidence of anthracnose in fruit that develop in the rainy season if no controls are applied. Growers usually apply fungicides, but even with management, this period is high-risk. A conservative expected prevalence of p ≈ 0.10 (10%) during the wet season is reasonable, reflecting that some level of infection/infestation (perhaps 1 in 10 trees showing symptoms) is fairly likely if a pest or pathogen is present. In outbreak scenarios or unmanaged orchards, prevalence could be higher, but 10% provides a baseline for "moderate" risk under typical management.

**Dry Season (e.g. May–October outside of flowering):** The dry season in Northern Australia is characterized by very low rainfall, lower humidity, and milder temperatures. These conditions are unfavorable for many diseases – for example, anthracnose severity is nearly zero on fruit that develop entirely in dry conditions. Pest activity is generally lower as well, since many insects have less lush growth or moisture to thrive on. Thus, we assume a very low prevalence, p ≈ 0.02 (2%), during the off-peak dry months. This implies only an occasional plant might show pest or disease symptoms in such conditions. Essentially, if a grower is surveying in the heart of the dry season, the expected pest incidence is minimal (possibly only persistent pests like some scales or mites at low levels).

| Season | Typical Pest/Disease Prevalence (p) |
|--------|-----------------------------------|
| Flowering Period (dry with dew) | ~0.05 (5%) |

**Flowering Period (dry season, typically late dry season when mangoes bloom):** Mango trees in Northern Australia usually flower during the dry season (often winter months). While the weather is dry, the flowering period brings its own pest and disease risks. Night-time dew and cooler mornings create pockets of humidity on blossoms, and certain pathogens and pests target flowers. A prime example is powdery mildew, which attacks mango inflorescences; it thrives in relatively dry, cool conditions with high overnight humidity. In fact, powdery mildew can cause up to 90% loss of blossoms in severe cases if untreated. Additionally, insects such as mango flower hoppers and midges are active during flowering, attracted to the blooms. With growers typically intervening (e.g., fungicide or insecticide sprays at flowering), the expected prevalence is moderated. We estimate p ≈ 0.05 (5%) during the flowering period as a typical value. This suggests a modest risk – perhaps one in twenty trees might show signs of powdery mildew or flower infestation under normal conditions with some control measures in place. Without any management, the prevalence could be much higher, but 5% reflects a scenario with common preventative measures (e.g. sulfur or other fungicide sprays that are often applied around flowering to combat powdery mildew).

These seasonal p values serve as defaults for the tool. In practice, growers would select the current season (or the closest equivalent period) in the web application, and the backend would apply the corresponding p. By using a higher p in the wet season and lower p in the dry, the required sample size will automatically scale up for high-risk periods and scale down when risk is low.

## Environmental Factors Influencing Pest Prevalence

Seasonal changes capture broad differences in weather, but specific environmental conditions – temperature, humidity, and rainfall – directly influence pest and disease prevalence. Understanding these influences can help refine the expected p (and could be used in future enhancements of the tool to adjust p dynamically). Below we explain each factor and how it might adjust the prevalence assumption:

**Temperature:** Most insect pests of mango (such as leafhoppers, thrips, fruit flies) are cold-blooded, so their reproduction and activity rates increase with warmer temperatures (up to an optimal threshold). In warm conditions, pests breed faster; for example, mango leaf hopper populations increase during warm periods. Thus, an abnormally warm season can lead to higher pest prevalence (higher p). On the other hand, extremely hot and dry conditions might slightly reduce some pests or stress disease pathogens (if, for instance, temperatures exceed the optimum for fungus growth or if heat kills delicate insect stages). As a guideline, if average temperatures are significantly above normal (e.g. ~5°C hotter than typical for that season), growers might expect pest incidence to be higher than the baseline – perhaps p should be nudged up by a few percentage points (for instance, a 5% baseline could be adjusted to 7% under an unusually hot spell). Conversely, cooler-than-normal conditions could slow pest life cycles, potentially lowering p slightly.

**Humidity:** Humidity has a strong impact on fungal diseases and some insect pests. Many fungal pathogens require high humidity to infect and spread. Mango anthracnose and other fruit rots, for example, thrive in wet, humid weather – high relative humidity allows spores to germinate on plant surfaces. Powdery mildew, interestingly, likes dry days but needs high overnight humidity (~90% RH) to cause severe infections. In practical terms, if a period is more humid than usual (e.g. an unusually humid dry season due to unseasonal rain or heavy dew), disease prevalence p should be set higher. If the tool in the future incorporates humidity data, one could add, say, +0.01–0.03 (1–3 percentage points) to p if the relative humidity is persistently high (near saturation at night or frequent dew). In contrast, if humidity is very low (e.g. a dry season with no dew), diseases like anthracnose or mildew will struggle – p could be adjusted downward (though in our seasonal defaults, dry season p is already very low). For example, a normally 10% wet-season p might be raised to 15% in a year with exceptional humidity and rainfall, reflecting a greater disease load, whereas a flowering-period p of 5% might drop to 2–3% if an unusual dry spell leads to very low humidity around bloom (thus less mildew).

**Rainfall:** Rainfall is closely tied to humidity and directly aids disease spread. Rain splashes spores and creates the wet surfaces needed for infection. As noted, if fruit development occurs in the rainy season, anthracnose incidence can exceed 90%. Heavy rains can also foster standing water and decaying fruit that attract pests like fruit flies. Therefore, above-average rainfall should prompt a higher assumed p. Later versions of the tool could incorporate recent rainfall data; for instance, if the last month had significantly more rain than average for that time of year, the tool might boost the prevalence estimate (perhaps moving the p to the wet-season level or higher). On the other hand, if a wet season turns out drier than normal (e.g., a weak monsoon with below-average rainfall), the grower's risk might be lower, and p could be adjusted slightly downward. As a recommendation, the app could categorize rainfall into bands (e.g. "low", "normal", "high") and adjust p accordingly – e.g., +0.05 to p for exceptionally high rainfall periods (since moisture is so critical, an unexpected rain in the dry season can trigger a small outbreak where normally there'd be none). It's worth noting that while rain generally increases pest issues, extremely heavy storms can occasionally knock down or reduce certain insect populations (for example, heavy rain can wash aphids or mites off leaves). However, the net effect of a rainy period in a tropical orchard is usually an increase in overall pest and disease prevalence, so the adjustments should reflect increased p with more rain.

In summary, high temperature (to a point), high humidity, and high rainfall all tend to increase pest/disease prevalence, raising the needed sample size. Cooler, drier conditions tend to suppress pests, lowering prevalence. If environmental data are integrated into the tool, they should modify the baseline seasonal p up or down. For example, one might implement simple rules like: "For every 50 mm of rainfall above normal this month, increase p by 0.01" or "If average RH > 85%, increase p by 0.02". These numbers can be refined with local research, but they illustrate the approach. By adjusting p in response to actual weather, the sample size recommendation becomes more tailored to the current risk level.

## Effect of Changing p, N, or Confidence on Sample Size

The required sample size n is sensitive to the inputs p, N, and the confidence level (via z-score). Understanding these relationships is important for both the developer and the user, as it explains why the tool might recommend more samples in some scenarios and fewer in others:

**Expected Prevalence (p):** The value of p influences the term p(1-p) in the formula. This term is maximized when p = 0.5 and is lower when p is near 0 or 1. In practical terms, if we expect a very low prevalence (say p = 0.01 or 1%), the required sample size for a given confidence and precision actually becomes smaller than if prevalence were moderate. This is because a 5% absolute margin of error is relatively large compared to a 1% prevalence (we are accepting a wide relative error). For example, with 95% confidence and 5% margin, assuming p = 0.50 (50%) would require about 385 samples (in an infinite population) to meet ±5% precision. But if p = 0.10 (10%), the initial sample size m drops (because 0.10×0.90 = 0.09, smaller than 0.25). Plugging into the formula:

m = (1.96² × 0.1 × 0.9) / 0.05² ≈ 138

Thus, expecting only 10% incidence means you need far fewer samples to estimate that rate within ±5%. In our context, this means during a low-risk season (dry season, p low), the recommended sample n will be much smaller than in a high-risk season (wet season, higher p). However, it's important to note that if p is extremely low, the interpretation shifts more toward detection of any cases rather than precise estimation. If a grower is aiming for early detection (catching at least one infected plant when p is very small), they might actually prefer using a detection probability formula rather than a margin-of-error formula. But given our approach, as p decreases, required n decreases. On the flip side, if one were to assume a very high p (approaching 50% or beyond), the sample size increases (up to the maximum at 50%). In summary, using a higher assumed prevalence yields a more conservative (larger) sample size recommendation, and using a lower p yields a smaller sample size.

**Confidence Level (z-score):** The confidence level selected by the user (90%, 95%, 99%) has a direct impact through the z-score. A higher confidence demands a larger n to achieve the same precision. The relationship is quadratic: for instance, going from 95% to 99% confidence increases z from 1.96 to 2.575, which roughly increases n by a factor of (2.575/1.96)² ≈ 1.73 (73% more samples). Conversely, dropping to 90% confidence (z ≈ 1.645) reduces the sample size requirement to about (1.645/1.96)² ≈ 0.70 (70%) of the 95% sample. In practical terms, if the user is okay with 90% confidence instead of 95%, the required sample might drop significantly. For example, assuming p=0.10, d=0.05, N large: 95% confidence gave m ≈ 138, whereas 90% confidence would give m ≈ (1.645² * 0.1 * 0.9)/0.0025 ≈ 96. The tool will allow the user to make this trade-off: higher confidence = more samples, lower confidence = fewer samples. This is a classic precision vs. effort trade-off in sampling.

**Population Size (N):** The total number of plants in the orchard bounds how many can/should be sampled. If N is very large (thousands of trees), then initially n grows with N until n plateaus at the infinite population requirement. Once N exceeds a certain point, the finite population correction has little effect (e.g., sampling 300 out of 10,000 vs 300 out of "infinite" population is almost the same). On the other hand, if N is not much larger than the initial m, the correction significantly lowers the required n. As N decreases, the required sample fraction becomes a larger portion of the population, so you don't need to sample as many to achieve the same confidence. This is because when the population is small, sampling without replacement yields more information about the whole. For example, if p=0.5, d=0.05, 95% confidence: infinite n ~ 385. But if N = 1000 (finite), plugging into the formula gives n ~ 278, which is about 28% of the population instead of 38.5%. If N is 200 (very small orchard), the formula might yield n around ~132 (instead of 385, because sampling 132 out of 200 covers a large portion). In the extreme case, if N is equal to or smaller than the infinite m, the formula will typically suggest sampling almost the entire population. Indeed, the formula will never return n larger than N – it inherently caps at N (if m > N, then 1 + (m-1)/N is big, pushing n toward N). In practice, the tool should enforce that as well: it makes no sense to sample more plants than exist, so we cap n at N. If N is very small (say a tiny orchard of 20 trees), and the user asks for 99% confidence, the best strategy is to just inspect all trees. The app can handle that automatically, since the calculation will likely return n = N in such cases. The general effect is: larger population = sample size approaches the asymptotic formula; smaller population = relatively smaller sample needed (as a fraction of N). This gives growers with fewer trees a bit of a "break" – they may not need to inspect quite as many as a percentage of their orchard compared to a large plantation to get the same confidence.

**(Margin of Error d):** Although the margin of error is fixed at 5% in this scenario, it's worth noting for completeness that d has a very strong inverse-square effect on n. If in the future the tool allowed different precision levels, a tighter margin (say 3%) would require roughly (5/3)² ≈ 2.78 times more samples than 5%. Conversely, a looser margin (10% error tolerance) would drastically cut n (down to about 25% of the samples needed for 5% margin). For now, we assume d = 0.05, but this explains why a relatively large error of 5% is chosen – it keeps sample sizes manageable for growers. A 5% precision is a reasonable balance between accuracy and effort.

In summary, increasing confidence or expected prevalence raises the required sample size, while having a finite (smaller) population or a lower expected prevalence lowers it. These relationships ensure the tool's output is intuitive: if a grower expects a bad outbreak (high p) or wants near-certainty (99% confidence), they will be advised to check many more plants. If they believe the risk is low or accept a bit more uncertainty, the sample can be smaller. The backend will calculate all this using the formula, so the user only needs to provide inputs in plain terms (number of trees, select season, select confidence level).

## Implementation in the Django Web App

With the formula and assumptions established, implementing this in a Django web application backend is straightforward. The application will need to gather user inputs, apply the formula, and return the result. Below is a clear flow of how the calculation function should operate:

1. **User Input:** The grower provides the required inputs via a form:
   - N: Total number of mango plants on the property (population size).
   - Confidence Level: Chosen from options (e.g. 90%, 95%, 99%). This will determine the z-score.
   - Season: Chosen from options (Wet season, Dry season, Flowering period). This will determine the baseline prevalence p to use. (In the future, this could be enhanced or replaced by more granular inputs like current temperature, humidity, etc., but for now season maps to a typical p value.)

2. **Parameter Mapping:** In the backend, the function will map the confidence level to the corresponding z-score. For example:
   - 90% confidence -> z ≈ 1.645
   - 95% confidence -> z ≈ 1.960
   - 99% confidence -> z ≈ 2.575

   These values can be stored in a dictionary or looked up. Similarly, map the selected season to the expected prevalence p. Using the typical values from Table 1:
   - Wet season -> p = 0.10
   - Dry season -> p = 0.02
   - Flowering period -> p = 0.05

   (These values might be refined or set in a configuration so that they could be updated as needed without code changes. They represent typical risk levels as discussed above.)

3. **Set Precision:** Set the margin of error d = 0.05 (5%). This is a constant in our current requirements.

4. **Calculate Initial Sample Size (m):** Using the formula for an infinite population, calculate
   m = (z² * p * (1-p)) / d²
   This yields a float which is the theoretical sample size needed if the orchard were very large.

5. **Apply Finite Population Correction:** Now incorporate the total plant count N to get n. Use:
   n = m / (1 + (m-1)/N)
   which is algebraically the same as n = (N * m) / ((m-1)+N). This adjusts n downward if N is not extremely large. If N is huge relative to m, this won't change n much. If N is only moderately larger than m, this will reduce n. If N < m, this formula will yield n slightly below N. (The function should be careful with data types, ensuring a float division is used so the math is correct, then later round up.)

6. **Ceiling and Cap:** Round n up to the nearest whole number (using `ceil` or equivalent) because you can only sample whole plants and rounding up ensures the error margin requirement is still met or exceeded. Also, enforce that n cannot exceed N. In the unlikely case that the math produces n larger than N (which mathematically shouldn't happen if the formula is applied correctly, except possibly if p was set to 0.5 and N is not huge), cap it: if `n > N`, then set `n = N`. This essentially means "sample all plants" if the formula demands more than the orchard size, which aligns with common sense.

7. **Output Result:** The function returns this final n as the recommended number of plants to inspect. This can be displayed to the user along with a message such as: "You should survey at least n plants to achieve ___% confidence of detecting the pest if it is present." The output can also contextualize by mentioning the assumptions (e.g., using a presumed prevalence of 10% for wet season).

For example, suppose a user enters N = 500 trees, selects 95% confidence and Wet season. The backend will map 95% -> z=1.96, wet -> p=0.10, and use d=0.05. The calculation would be:

m = (1.96² × 0.1 × 0.9) / 0.05² ≈ 138.3.

Finite correction
n = 138.3 / (1+ (138.3-1)/500) ≈ 138.3 / (1+0.2746) ≈ 138.3 / 1.2746 ≈ 108.5.

Rounded up, n = 109 plants.

Thus, the app would recommend inspecting 109 out of 500 trees under those conditions. If the user switched to 90% confidence, the calculation would yield a smaller number (around 77 plants for the same p and N). If the user instead had N = 100 trees with the same settings, the formula would give something close to n = 86 (because with fewer total trees, you end up needing to check a larger fraction of them to get 95% confidence). And if the user had N = 50 trees, it might suggest ~44 (almost the whole orchard). These examples align with expectations and can be verified against known sample size tables.

The formula and logic described are directly implementable in a Django view or utility function. Here is a pseudo-code outline for clarity:

```python
def calculate_sample_size(N, confidence_level, season):
    # 1. Map confidence to z-score
    z_map = {'90%': 1.645, '95%': 1.960, '99%': 2.575}
    z = z_map[confidence_level]
    
    # 2. Map season to prevalence p
    p_map = {'Wet': 0.10, 'Dry': 0.02, 'Flowering': 0.05}
    p = p_map[season]
    
    # 3. Set margin of error
    d = 0.05
    
    # 4. Calculate m (initial sample size for infinite population)
    m = (z**2 * p * (1 - p)) / (d**2)
    
    # 5. Finite population correction
    n = m / (1 + (m - 1) / N)
    
    # 6. Round up and cap at N
    n = math.ceil(n)
    if n > N:
        n = N
        
    return n
```

(The actual implementation might include input validation and formatting of the result, but the above logic covers the core calculation.)

The Django view would call this function after form submission and then render the result in the template for the user. All citations and assumptions (like the chosen p values) can be documented in the app's help section so users understand why those numbers are used.

## Conclusion and Recommendations

By following the above approach, we ensure the web application provides scientifically grounded advice on surveillance effort. The use of a standard sample size formula for proportions (with finite population correction) gives the tool a robust statistical basis. The seasonal prevalence values we introduced are based on real agronomic conditions in Northern Australia – wet season conditions dramatically heighten disease incidence, while a defined dry season keeps disease almost nil, and flowering brings specific risks like powdery mildew outbreaks. These values (and future environmental factor adjustments) make the recommendations practical and tailored to the grower's situation.

For implementation, careful structuring of the code and clear commenting will make it easy to update the logic. For instance, if new research suggests different typical prevalences or if the tool is expanded to other crops, one can adjust the p values or add new profiles. Likewise, the mapping of confidence levels to z-scores could be extended if more options are needed.

Finally, it's advised to include guidance in the app UI about interpreting the results. Growers should understand that the recommended sample size gives them (for example) 95% confidence of detecting a pest if ~10% of their trees were infested. If a pest could be even rarer, they might choose a higher confidence or simply know that no practical sample can ever guarantee finding a 1-in-10000 occurrence. In essence, this tool empowers growers to allocate scouting resources effectively, focusing efforts when and where the risk is highest. By implementing the formula and seasonal risk model described above, the Django application will be a valuable decision-support tool for mango pest and disease surveillance in Northern Australia.

## Sources:
- Statistical formula for sample size with finite population correction.
- Effect of dry vs. wet season on mango anthracnose incidence.
- Powdery mildew risk during flowering in dry conditions.
- Insect pest activity in warm weather (mango leafhopper example).
- Illustrative sample size calculations and effects of population size.

## Citations
- 6.3 - Estimating a Proportion for a Small, Finite Population | STAT 415
  https://online.stat.psu.edu/stat415/lesson/6/6.3
- https://www.mango.org/wp-content/uploads/2020/08/Mango_Pests_and_Diseases_ENG.pdf
- Alleviating biotic stress of powdery mildew in mango cv. Keitt by Sulfur nano...
  https://www.nature.com/articles/s41598-025-88282-z
- Most Common Pests Affecting Mangoes | Wikifarmer
  https://wikifarmer.com/library/en/article/most-common-pests-affecting-mangoes
- https://www.ctahr.hawaii.edu/oc/freepubs/pdf/pd-48.pdf
- Finding The Right Sample Size (The Hard Way) - Eval Academy
  https://www.evalacademy.com/articles/finding-the-right-sample-size-the-hard-way

### All Sources
online.stat.psu mango nature wikifarmer ctahr.hawaii evalacademy
