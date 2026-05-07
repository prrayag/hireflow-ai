# HireFlow AI: Big Data & Analytics Architecture Guide

This document is designed to help you explain the Big Data, Storage, and Visualization architecture of the HireFlow AI project to your professor. It covers the exact justifications for the tech stack, details about Hadoop/Spark execution, and how the real-time dashboard works.

---

## 1. The Dataset (`resumes_100k.csv`)

### What is the dataset?
For the Big Data component of this project, we utilize a large-scale dataset (`resumes_100k.csv`). As seen in the HDFS screenshots, this file contains structured candidate profiles with fields like: `Name, Skills, Experience Years, Education Level`. 

### Justification for using it: (The 5 V's of Big Data)
To justify the use of Big Data technologies like Hadoop and Spark, our HR dataset architecture demonstrates the classic "5 V's":

1. **Volume:** Processing hundreds of thousands (or millions) of resumes. A standard web backend (like Flask with standard Python lists) or Pandas would choke or consume too much RAM when performing complex group-by operations on this much data.
2. **Velocity:** In a real-world scenario like LinkedIn, thousands of resumes are uploaded every minute. Our architecture handles the fast streaming of new uploads through the web app while Spark processes the heavy historical batches.
3. **Variety:** Resumes are highly unstructured. Some are PDFs, some are DOCX, some have 5 skills, others have 20. Our pipeline handles this variety by parsing unstructured text into a unified JSON format.
4. **Veracity:** Data quality is messy. OCR extraction can fail, and applicants misspell skills. We handle veracity by using AI (TabTransformer and NLP) to clean, standardize, and score the messy data accurately.
5. **Value:** The ultimate goal of Big Data is extracting value. We transform raw, unreadable resumes into a ranked, dynamic dashboard, allowing HR managers to make hiring decisions in seconds instead of hours.

---

## 2. Hadoop & HDFS (Hadoop Distributed File System)

### Why did we use Hadoop?
We needed a reliable, distributed storage system to hold massive datasets that exceed the storage capacity or processing power of a single machine. 

### What is happening in your screenshots?
Your screenshots show a local Hadoop cluster running on Windows:
*   **`jps` output:** Shows the core Hadoop daemons running:
    *   **NameNode:** The master node that tracks *where* data blocks are stored.
    *   **DataNode:** The worker node that actually stores the chunks of the `resumes_100k.csv` file.
    *   **ResourceManager & NodeManager (YARN):** These manage the CPU and memory resources for any distributed jobs (like Spark) running on the cluster.
*   **`hadoop fs -put` and `hadoop fs -ls /`:** You uploaded the dataset and the raw `100_resumes.zip` directly into HDFS. This splits the files into 128MB blocks across DataNodes, ensuring fault tolerance (replication) and allowing parallel processing.

---

## 3. Apache Spark (The Distributed Processing Engine)

### Why Spark instead of Hadoop MapReduce?
While Hadoop provides HDFS for *storage*, we use Apache Spark for *processing* because it performs **in-memory computation**, making it up to 100x faster than traditional MapReduce (which constantly reads/writes to disk).

### Expected Spark Architecture (For the Viva/Professor)
When the professor asks how Spark executes the resume analytics, point them exactly to the `spark_rdd_pipeline.py` execution:

**We created 4 main Spark Jobs, approximately 10 Stages (due to network shuffles), and exactly 18 RDD operations.**

Here is the exact breakdown of the 4 Jobs:
1. **Job 1 (Ingest & Clean):** Loads the 100,000 resumes. Filters out null or corrupted rows to ensure **Veracity**.
2. **Job 2 (TF-IDF Feature Extraction):** Calculates the Term Frequency-Inverse Document Frequency (TF-IDF) across the entire 100k dataset to find the most unique, high-value skills.
3. **Job 3 (Scoring & Ranking):** Calculates the AI score for every candidate simultaneously and performs a global distributed sort (`sortByKey`) to rank them from #1 to #100,000.
4. **Job 4 (Analytics Aggregation):** Runs the heavy group-by operations: calculating the Average Score by Education Level (Bachelors, Masters, etc.) and grouping scores into Histogram bands.

### The 18-Step RDD Lineage (The DAG)
If asked about the transformations (lazy) and actions (triggers), explain this exact lineage:

1. `parallelize()` - Loads raw dataset into an RDD.
2. `filter()` - Drops invalid rows.
3. `map()` - Extracts `(name, skills)` tuples.
4. `flatMap()` - Tokenizes the comma-separated skills.
5. **`reduceByKey()`** - Calculates Term Frequency **[Triggers a Network SHUFFLE]**.
6. `map()` - Prepares Document Frequency pairs.
7. **`reduceByKey()`** - Calculates Document Frequency **[SHUFFLE]**.
8. `map()` - Remaps data for the join.
9. **`join()`** - Joins TF and IDF scores together **[SHUFFLE]**.
10. `map()` - Final TF-IDF mathematical calculation.
11. `map()` - Assigns final AI score per candidate.
12. **`sortByKey()`** - Global sorting for ranking **[SHUFFLE]**.
13. `zipWithIndex().map()` - Assigns the final rank number (1, 2, 3...).
14. `map()` - Prepares `(Education, Score)` pairs.
15. **`groupByKey()`** - Groups scores by degree **[SHUFFLE]**.
16. `mapValues()` - Averages the scores inside each group.
17. `map()` - Prepares `(ScoreBand, Count)` pairs.
18. **`reduceByKey()`** - Calculates the final Band Histogram counts **[SHUFFLE]**.

---

## 4. Database Justification: Why MongoDB instead of HDFS?

A common professor question is: *"If you have Hadoop/HDFS, why are you also using MongoDB?"*

**Answer: We implemented a Lambda-style Architecture separating Batch and Speed layers.**

*   **HDFS & Spark (The Batch Layer):** 
    *   *Characteristics:* High latency, massive throughput. 
    *   *Use case:* Best for processing the massive `resumes_100k.csv` file overnight to find macro-trends (e.g., "What is the most demanded skill of 2026?"). It takes seconds/minutes to start a job, which is too slow for a web user.
*   **MongoDB (The Speed/Serving Layer):**
    *   *Characteristics:* Low latency, document-based flexible schema.
    *   *Use case:* Best for the live Web Application. When an HR manager uploads 5 resumes on the website, they need the scores rendered on the dashboard in milliseconds. MongoDB stores these incoming JSON documents instantly.
    *   *Why NoSQL?* Resumes are highly unstructured. Some have 5 skills, some have 20. Some have missing contact info. MongoDB’s schema-less JSON format perfectly matches the output of our AI Resume Parser.

---

## 5. Visualizations & Real-Time Dashboard

### How the Visualizations Work (No Hardcoding)
The analytics dashboard is built to be entirely dynamic. Here is the exact flow:

1. **The Source of Truth:** Every time a new resume is scored by the AI (TabTransformer), the resulting JSON object (containing the score, extracted skills, and experience) is saved to MongoDB.
2. **The Aggregation (Backend):** The Flask backend exposes an `/api/analytics-data` endpoint. When requested, Python queries MongoDB and dynamically calculates the metrics:
   *   *Score Distribution:* Python loops through all candidates and buckets them into `10-20%`, `20-30%`, etc.
   *   *Hiring Funnel:* It runs live `.count()` operations on the data (Total Uploaded → Parsed Successfully → Score > 50%).
3. **The Rendering (Frontend):** The React frontend uses **Chart.js** (`react-chartjs-2`). It fetches the JSON from the API and binds it to the charts. 

### Justification for Chart.js
We chose Chart.js on the client side over generating static plots (like Python Matplotlib PNGs) because:
*   **Interactivity:** Users can hover over the bars to see exact numbers and tooltips.
*   **Real-time Auto-refresh:** The React `useEffect` hook polls the backend API every 30 seconds. If a new resume is processed, the charts animate and update automatically without requiring a page reload.
*   **Offloading Compute:** Having the user's browser render the graphics saves CPU cycles on the backend server, allowing the backend to focus entirely on AI scoring and database queries.

## 6. Tricky / Common Viva Questions (And How to Answer Them)

**Q1: "I see your `resumes_100k.csv` file size is around 5.4MB. Why do you need a Hadoop cluster for 5MB? That fits in the RAM of a smartphone."**
*   **The Trap:** The professor is testing if you actually understand when Big Data is necessary, versus just throwing buzzwords around.
*   **How to answer:** "Sir/Ma'am, you are absolutely correct; 5MB easily fits in local memory and Pandas could process it in milliseconds. However, this project is a *scaled-down prototype* for academic demonstration. In a real production environment (like LinkedIn or Indeed), HR datasets contain terabytes of full-text embeddings, not just a CSV summary. We used this 100k synthetic dataset to *demonstrate* and *prove* that our distributed architecture (HDFS, YARN, Spark DAGs) works. The PySpark code we wrote will scale seamlessly whether the file is 5MB or 500GB."

**Q2: "What happens if there are null values or broken commas in your `resumes_100k.csv` when Spark reads it?"**
*   **How to answer:** "When reading the CSV into a Spark DataFrame, we use options like `mode='DROPMALFORMED'` to automatically drop rows with corrupted data or missing columns. Alternatively, we use RDD `.filter()` transformations to clean out null values before they reach the `reduceByKey` action, ensuring our final analytics aren't skewed by dirty data."

**Q3: "Did you write MapReduce code for this?"**
*   **The Trap:** They want to see if you know the difference between Hadoop MapReduce and Apache Spark.
*   **How to answer:** "No, we did not write traditional Java MapReduce code. We used Apache Spark. While Hadoop HDFS handles the *storage*, Spark handles the *processing*. Spark uses in-memory RDDs/DataFrames and executes transformations via a Directed Acyclic Graph (DAG). This means the map and reduce phases happen in-memory without constantly writing intermediate results to the hard drive, making it up to 100x faster than Hadoop MapReduce."

**Q4: "Since your file is 5.4MB, how many Partitions will Spark create when it reads it?"**
*   **The Trap:** Testing your knowledge of HDFS block sizes.
*   **How to answer:** "The default block size in Hadoop 3.x is 128MB. Because our file is only 5.4MB, HDFS stores the entire file inside a single block. Therefore, when Spark reads it natively from HDFS, it will default to creating just **1 partition** (though it might distribute it up to the default parallelism of the cluster's cores). If we had a 200MB file, it would span two blocks and Spark would create at least two partitions."

**Q5: "Can you explain the DAG for a simple job, like counting the most popular skills?"**
*   **How to answer:** "Yes. The DAG (Directed Acyclic Graph) would have two main stages separated by a shuffle. 
    1.  **Stage 1 (Map):** Spark reads the CSV, extracts the 'Skills' column, and performs a `flatMap` to split the comma-separated skills. It then maps each skill to a tuple like `(Python, 1)`.
    2.  **Shuffle:** Data is shuffled across the network so all identical keys (e.g., all 'Python's) go to the same worker node.
    3.  **Stage 2 (Reduce):** Spark performs a `reduceByKey` to sum the counts `(Python, 10450)`. 
    Finally, an action like `.collect()` triggers this entire DAG execution."
