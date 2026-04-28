drop database ModBankFraudAnalysis

create database ModBankFraudAnalysis

USE ModBankFraudAnalysis;
GO


-- =============================================================
-- HOUSEKEEPING
-- Dedicated schema keeps warehouse objects out of dbo,
-- which makes permission grants and restores cleaner.
-- Fact dropped first to satisfy FK dependency order.
-- =============================================================
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dw')
    EXEC('CREATE SCHEMA dw AUTHORIZATION dbo');
GO

IF OBJECT_ID('dw.Fact_BankTransaction', 'U') IS NOT NULL DROP TABLE dw.Fact_BankTransaction;
IF OBJECT_ID('dw.Dim_Account',          'U') IS NOT NULL DROP TABLE dw.Dim_Account;
IF OBJECT_ID('dw.Dim_Device',           'U') IS NOT NULL DROP TABLE dw.Dim_Device;
IF OBJECT_ID('dw.Dim_TransactionType',  'U') IS NOT NULL DROP TABLE dw.Dim_TransactionType;
IF OBJECT_ID('dw.Dim_Merchant',         'U') IS NOT NULL DROP TABLE dw.Dim_Merchant;
IF OBJECT_ID('dw.Dim_Location',         'U') IS NOT NULL DROP TABLE dw.Dim_Location;
IF OBJECT_ID('dw.Dim_Customer',         'U') IS NOT NULL DROP TABLE dw.Dim_Customer;
IF OBJECT_ID('dw.Dim_Time',             'U') IS NOT NULL DROP TABLE dw.Dim_Time;
IF OBJECT_ID('dw.Dim_Date',             'U') IS NOT NULL DROP TABLE dw.Dim_Date;
GO


-- =====================================================================
-- SECTION 1  -  DIMENSIONS
-- =====================================================================


-- ---------------------------------------------------------------------
-- Dim_Date
--
-- DateKey is YYYYMMDD as an INT, not a DATE column.
-- It joins faster on large fact tables and stays readable
-- when you're browsing the data raw.  No IDENTITY needed
-- since the key is computed, not generated.
--
-- Fiscal calendar follows Indian FY (Apr-Mar).
-- FiscalYear = the year the FY starts, so Apr 2024 = FY 2024.
-- IsHoliday defaults to 0; populate it from an RBI calendar
-- feed if the team wants holiday-adjusted reporting later.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Date (
    DateKey             INT          NOT NULL,
    FullDate            DATE         NOT NULL,

    -- day-level
    DayOfWeek           TINYINT      NOT NULL,   -- 1=Sun ... 7=Sat
    DayName             NVARCHAR(10) NOT NULL,
    DayOfMonth          TINYINT      NOT NULL,
    DayOfYear           SMALLINT     NOT NULL,
    WeekOfYear          TINYINT      NOT NULL,
    IsWeekend           BIT          NOT NULL,
    IsLastDayOfMonth    BIT          NOT NULL,

    -- month / quarter
    MonthNumber         TINYINT      NOT NULL,
    MonthName           NVARCHAR(10) NOT NULL,
    MonthNameShort      NCHAR(3)     NOT NULL,
    CalendarQuarter     TINYINT      NOT NULL,
    CalendarYear        SMALLINT     NOT NULL,

    -- Indian fiscal year
    FiscalYear          SMALLINT     NOT NULL,
    FiscalQuarter       TINYINT      NOT NULL,
    FiscalMonthNumber   TINYINT      NOT NULL,   -- Apr = 1, Mar = 12
    FiscalYearLabel     NCHAR(7)     NOT NULL,   -- 'FY24-25'

    -- placeholder for RBI / bank holidays
    IsHoliday           BIT          NOT NULL CONSTRAINT DF_DimDate_Holiday DEFAULT 0,
    HolidayName         NVARCHAR(60) NULL,

    CONSTRAINT PK_Dim_Date PRIMARY KEY CLUSTERED (DateKey)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Time
--
-- Hour granularity only (24 rows).  The source data has a TIME
-- column but all the fraud analysis in the original script works
-- at the hour level, so this is fine.  If minute-level analysis
-- is ever needed, the TimeKey can be switched to HHMM without
-- touching the fact table structure.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Time (
    TimeKey         TINYINT      NOT NULL,   -- 0-23
    HourLabel       NCHAR(5)     NOT NULL,   -- '09:00'
    HourNumber      TINYINT      NOT NULL,
    TimePeriod      NVARCHAR(20) NOT NULL,   -- Late Night / Morning / Afternoon / Evening
    TimePeriodCode  NCHAR(2)     NOT NULL,   -- LN / MO / AF / EV
    IsPeakHour      BIT          NOT NULL,   -- 09-11 h and 18-20 h

    CONSTRAINT PK_Dim_Time PRIMARY KEY CLUSTERED (TimeKey)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Customer  [SCD Type 2]
--
-- Customer name, age, and contact details can change between
-- transactions.  SCD2 means we can answer "how old was this
-- customer when the fraud happened" correctly, not just "how old
-- are they today".
--
-- RowHash is SHA2_256 over all tracked columns.  One hash comparison
-- per row in the ETL MERGE beats checking every column individually,
-- and collisions are not a real concern at this scale.
--
-- The filtered unique index on IsCurrent=1 keeps current-row lookups
-- fast without bloating the index as history accumulates.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Customer (
    CustomerSK          INT           NOT NULL IDENTITY(1,1),

    Customer_ID         VARCHAR(50)   NOT NULL,   -- natural key

    -- SCD2-tracked columns
    Customer_Name       NVARCHAR(100) NOT NULL,
    Gender              NVARCHAR(10)  NOT NULL,
    Age                 TINYINT       NOT NULL,
    AgeGroup            NVARCHAR(10)  NOT NULL,   -- stored so queries don't repeat the CASE
    Customer_Contact    NVARCHAR(50)  NULL,
    Customer_Email      NVARCHAR(150) NULL,

    -- versioning
    RowEffectiveDate    DATE          NOT NULL,
    RowExpiryDate       DATE          NOT NULL CONSTRAINT DF_DimCustomer_Expiry  DEFAULT '9999-12-31',
    IsCurrent           BIT           NOT NULL CONSTRAINT DF_DimCustomer_Current DEFAULT 1,
    RowHash             NCHAR(64)     NOT NULL,

    -- audit
    InsertedAt          DATETIME2(0)  NOT NULL CONSTRAINT DF_DimCustomer_Ins DEFAULT SYSUTCDATETIME(),
    UpdatedAt           DATETIME2(0)  NOT NULL CONSTRAINT DF_DimCustomer_Upd DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_Customer PRIMARY KEY CLUSTERED (CustomerSK)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Location
--
-- Hierarchy: IndiaRegion > State > City > Bank_Branch > Transaction_Location
-- IndiaRegion is derived in the ETL from the state name.
-- SCD1 (overwrite) - no need to version geographic reference data.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Location (
    LocationSK           INT           NOT NULL IDENTITY(1,1),
    Transaction_Location NVARCHAR(150) NOT NULL,
    Bank_Branch          NVARCHAR(100) NOT NULL,
    City                 NVARCHAR(50)  NOT NULL,
    State                NVARCHAR(50)  NOT NULL,
    IndiaRegion          NVARCHAR(20)  NOT NULL,   -- North/South/East/West/Central/Northeast

    InsertedAt           DATETIME2(0)  NOT NULL CONSTRAINT DF_DimLocation_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_Location PRIMARY KEY CLUSTERED (LocationSK)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Merchant
--
-- MerchantCategoryGroup rolls individual categories up to an
-- executive level (8 groups vs. 20+ raw categories).
-- IsHighRiskCategory is baked in here so the fraud dashboards
-- don't need to hard-code category lists.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Merchant (
    MerchantSK            INT          NOT NULL IDENTITY(1,1),
    Merchant_ID           VARCHAR(50)  NOT NULL,
    Merchant_Category     NVARCHAR(50) NOT NULL,
    MerchantCategoryGroup NVARCHAR(40) NOT NULL,
    IsHighRiskCategory    BIT          NOT NULL,

    InsertedAt            DATETIME2(0) NOT NULL CONSTRAINT DF_DimMerchant_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_Merchant PRIMARY KEY CLUSTERED (MerchantSK)
);
GO


-- ---------------------------------------------------------------------
-- Dim_TransactionType
--
-- IsHighRiskType flags Transfer and Withdrawal, matching the
-- original risk-scoring model.  Putting it here means the fact
-- ETL and analysis queries don't repeat that logic.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_TransactionType (
    TransactionTypeSK  INT          NOT NULL IDENTITY(1,1),
    Transaction_Type   NVARCHAR(30) NOT NULL,
    TypeGroup          NVARCHAR(20) NOT NULL,   -- Debit / Credit / Other
    IsHighRiskType     BIT          NOT NULL,
    IsDebit            BIT          NOT NULL,
    IsCredit           BIT          NOT NULL,

    InsertedAt         DATETIME2(0) NOT NULL CONSTRAINT DF_DimTxnType_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_TransactionType PRIMARY KEY CLUSTERED (TransactionTypeSK)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Device
--
-- The source has two device columns: Device_Type (broad category)
-- and Transaction_Device (specific label after the Step 5 cleanup).
-- Both are kept here so the fact table needs only one FK.
-- DeviceChannel (Digital / Physical) is a useful axis that wasn't
-- in the original script at all.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Device (
    DeviceSK           INT           NOT NULL IDENTITY(1,1),
    Device_Type        NVARCHAR(30)  NOT NULL,
    Transaction_Device NVARCHAR(100) NOT NULL,
    DeviceChannel      NVARCHAR(20)  NOT NULL,   -- Digital / Physical / Hybrid
    IsDigitalChannel   BIT           NOT NULL,
    IsHighRiskDevice   BIT           NOT NULL,   -- Mobile + ATM flagged in original model

    InsertedAt         DATETIME2(0)  NOT NULL CONSTRAINT DF_DimDevice_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_Device PRIMARY KEY CLUSTERED (DeviceSK)
);
GO


-- ---------------------------------------------------------------------
-- Dim_Account
--
-- Account_Type + Transaction_Currency as a combination dimension.
-- AccountCategory (Savings / Current / Other) gives analysts a
-- cleaner grouping than the raw Account_Type values.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Dim_Account (
    AccountSK            INT          NOT NULL IDENTITY(1,1),
    Account_Type         NVARCHAR(30) NOT NULL,
    Transaction_Currency NCHAR(3)     NOT NULL,
    AccountCategory      NVARCHAR(20) NOT NULL,
    IsRetailAccount      BIT          NOT NULL,

    InsertedAt           DATETIME2(0) NOT NULL CONSTRAINT DF_DimAccount_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Dim_Account PRIMARY KEY CLUSTERED (AccountSK)
);
GO


-- =====================================================================
-- SECTION 2  -  FACT TABLE
-- =====================================================================

-- ---------------------------------------------------------------------
-- Fact_BankTransaction
--
-- Grain: one row per bank transaction.
--
-- Measure notes:
--   Transaction_Amount       additive - sum freely across any dimension
--   Account_Balance          semi-additive - averaging is fine, summing
--                            is not (point-in-time snapshot)
--   Amount_to_Balance_Ratio  non-additive - average only
--   Is_Fraud                 additive as an integer flag
--   Risk_Score               non-additive - average or count-by-bucket
--
-- Transaction_ID stays in the fact as a degenerate dimension.
-- It's a unique identifier with no descriptive attributes, so
-- there's no reason to build a separate dimension table for it.
--
-- Amount_Category, Balance_Risk_Flag, and Risk_Score are all
-- pre-computed at load time.  In the original script these were
-- inline CASE blocks that appeared five or six times each.
-- Storing them once is cleaner and lets us index Risk_Score
-- for fast high-risk transaction lookups.
-- ---------------------------------------------------------------------
CREATE TABLE dw.Fact_BankTransaction (
    TransactionSK           INT           NOT NULL IDENTITY(1,1),

    -- degenerate dimension (source natural key)
    Transaction_ID          VARCHAR(50)   NOT NULL,

    -- foreign keys
    DateKey                 INT           NOT NULL,
    TimeKey                 TINYINT       NOT NULL,
    CustomerSK              INT           NOT NULL,
    LocationSK              INT           NOT NULL,
    MerchantSK              INT           NOT NULL,
    TransactionTypeSK       INT           NOT NULL,
    DeviceSK                INT           NOT NULL,
    AccountSK               INT           NOT NULL,

    -- additive measures
    Transaction_Amount      DECIMAL(18,2) NOT NULL,

    -- semi-additive  (balance snapshot at moment of transaction)
    Account_Balance         DECIMAL(18,2) NOT NULL,

    -- non-additive derived measure  (NULL when balance is zero)
    Amount_to_Balance_Ratio DECIMAL(10,4) NULL,

    -- fraud signal
    Is_Fraud                TINYINT       NOT NULL DEFAULT 0,

    -- pre-computed risk score (0-6 composite, matches original Step 7 formula)
    Risk_Score              TINYINT       NOT NULL DEFAULT 0,

    -- pre-computed category flags (stored to avoid repeated CASE blocks)
    Amount_Category         NVARCHAR(10)  NOT NULL,   -- Low/Medium/High/Very High
    Balance_Risk_Flag       NVARCHAR(12)  NOT NULL,   -- Low Risk/Medium Risk/High Risk/Unknown

    -- kept for drill-through; not used for aggregation
    Transaction_Description NVARCHAR(500) NULL,

    InsertedAt              DATETIME2(0)  NOT NULL CONSTRAINT DF_Fact_Ins DEFAULT SYSUTCDATETIME(),

    CONSTRAINT PK_Fact_BankTransaction  PRIMARY KEY CLUSTERED (TransactionSK),
    CONSTRAINT FK_Fact_Date             FOREIGN KEY (DateKey)           REFERENCES dw.Dim_Date(DateKey),
    CONSTRAINT FK_Fact_Time             FOREIGN KEY (TimeKey)           REFERENCES dw.Dim_Time(TimeKey),
    CONSTRAINT FK_Fact_Customer         FOREIGN KEY (CustomerSK)        REFERENCES dw.Dim_Customer(CustomerSK),
    CONSTRAINT FK_Fact_Location         FOREIGN KEY (LocationSK)        REFERENCES dw.Dim_Location(LocationSK),
    CONSTRAINT FK_Fact_Merchant         FOREIGN KEY (MerchantSK)        REFERENCES dw.Dim_Merchant(MerchantSK),
    CONSTRAINT FK_Fact_TransactionType  FOREIGN KEY (TransactionTypeSK) REFERENCES dw.Dim_TransactionType(TransactionTypeSK),
    CONSTRAINT FK_Fact_Device           FOREIGN KEY (DeviceSK)          REFERENCES dw.Dim_Device(DeviceSK),
    CONSTRAINT FK_Fact_Account          FOREIGN KEY (AccountSK)         REFERENCES dw.Dim_Account(AccountSK)
);
GO


-- =====================================================================
-- SECTION 3  -  INDEXES
-- =====================================================================

-- Dimension natural-key indexes
-- These serve two purposes: fast lookup during ETL MERGE, and
-- uniqueness enforcement so bad source data doesn't slip through.

-- Filtered on IsCurrent=1 so the index stays small as SCD2 history grows.
-- The hash index beside it is what the ETL MERGE actually hits first.
CREATE UNIQUE NONCLUSTERED INDEX UX_DimCustomer_Current
    ON dw.Dim_Customer (Customer_ID)
    WHERE IsCurrent = 1;
GO

CREATE NONCLUSTERED INDEX IX_DimCustomer_HashLookup
    ON dw.Dim_Customer (Customer_ID, RowHash)
    WHERE IsCurrent = 1;
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_DimLocation_NK
    ON dw.Dim_Location (State, City, Bank_Branch, Transaction_Location);
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_DimMerchant_NK
    ON dw.Dim_Merchant (Merchant_ID);
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_DimTxnType_NK
    ON dw.Dim_TransactionType (Transaction_Type);
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_DimDevice_NK
    ON dw.Dim_Device (Device_Type, Transaction_Device);
GO

CREATE UNIQUE NONCLUSTERED INDEX UX_DimAccount_NK
    ON dw.Dim_Account (Account_Type, Transaction_Currency);
GO


-- Fact table indexes
-- Each one is tailored to a specific query pattern from the
-- analysis layer.  INCLUDE columns are chosen to cover the
-- SELECT list and avoid key lookups on the clustered index.

-- Blocks duplicate loads; also used as the idempotent guard in ETL.
CREATE UNIQUE NONCLUSTERED INDEX UX_Fact_TxnID
    ON dw.Fact_BankTransaction (Transaction_ID);
GO

-- Monthly trend queries and any aggregation by date + fraud flag.
CREATE NONCLUSTERED INDEX IX_Fact_Date_Fraud
    ON dw.Fact_BankTransaction (DateKey, Is_Fraud)
    INCLUDE (Transaction_Amount, Risk_Score, CustomerSK, TransactionTypeSK);
GO

-- Customer-level fraud history and risk segmentation.
CREATE NONCLUSTERED INDEX IX_Fact_Customer_Fraud
    ON dw.Fact_BankTransaction (CustomerSK, Is_Fraud)
    INCLUDE (DateKey, Transaction_Amount, Risk_Score, Amount_to_Balance_Ratio);
GO

-- Merchant and device fraud pattern queries.
CREATE NONCLUSTERED INDEX IX_Fact_Merchant
    ON dw.Fact_BankTransaction (MerchantSK)
    INCLUDE (Transaction_Amount, Is_Fraud);
GO

CREATE NONCLUSTERED INDEX IX_Fact_Device_Fraud
    ON dw.Fact_BankTransaction (DeviceSK, Is_Fraud)
    INCLUDE (Transaction_Amount, Risk_Score);
GO

-- Risk score range scans - the drill-through and validation queries
-- both order and filter on this column.
CREATE NONCLUSTERED INDEX IX_Fact_RiskScore
    ON dw.Fact_BankTransaction (Risk_Score DESC, Is_Fraud)
    INCLUDE (CustomerSK, DateKey, Transaction_Amount);
GO

-- Hour-of-day fraud analysis.
CREATE NONCLUSTERED INDEX IX_Fact_Time_Fraud
    ON dw.Fact_BankTransaction (TimeKey, Is_Fraud)
    INCLUDE (Transaction_Amount);
GO

-- State + account type fraud breakdown.
CREATE NONCLUSTERED INDEX IX_Fact_Location_Account
    ON dw.Fact_BankTransaction (LocationSK, AccountSK)
    INCLUDE (Transaction_Amount, Is_Fraud);
GO


-- =====================================================================
-- SECTION 4  -  ETL: LOAD DIMENSIONS
-- All dimensions must be loaded before the fact table.
-- Every block here is idempotent - safe to re-run after a failure.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 4.1  Dim_Date  -  set-based tally, no cursor
--
-- Generates 2020-01-01 through 2030-12-31 (~4,018 rows).
-- The tally CTE cross-joins small tables to build a large
-- sequential number set, then DATEADD projects each number
-- onto a calendar date.  Much faster than a WHILE loop and
-- doesn't hammer tempdb with row-by-row inserts.
--
-- Adjust the start/end dates if the source data extends outside
-- this range; the WHERE clause handles the trim cleanly.
-- ---------------------------------------------------------------------
;WITH
  L0   AS (SELECT 1 c UNION ALL SELECT 1),
  L1   AS (SELECT 1 c FROM L0 a, L0 b),
  L2   AS (SELECT 1 c FROM L1 a, L1 b),
  L3   AS (SELECT 1 c FROM L2 a, L2 b),
  L4   AS (SELECT 1 c FROM L3 a, L3 b),
  Nums(n) AS (SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 FROM L4),
  Cal(d)  AS (
      SELECT DATEADD(DAY, n, CAST('2020-01-01' AS DATE))
      FROM Nums
      WHERE DATEADD(DAY, n, CAST('2020-01-01' AS DATE)) <= '2030-12-31'
  )
INSERT INTO dw.Dim_Date (
    DateKey, FullDate,
    DayOfWeek, DayName, DayOfMonth, DayOfYear,
    WeekOfYear, IsWeekend, IsLastDayOfMonth,
    MonthNumber, MonthName, MonthNameShort,
    CalendarQuarter, CalendarYear,
    FiscalYear, FiscalQuarter, FiscalMonthNumber, FiscalYearLabel
)
SELECT
    YEAR(d)*10000 + MONTH(d)*100 + DAY(d),
    d,
    DATEPART(WEEKDAY, d),
    DATENAME(WEEKDAY, d),
    DAY(d),
    DATEPART(DAYOFYEAR, d),
    DATEPART(WEEK, d),
    CASE WHEN DATEPART(WEEKDAY, d) IN (1,7) THEN 1 ELSE 0 END,
    CASE WHEN d = EOMONTH(d) THEN 1 ELSE 0 END,
    MONTH(d),
    DATENAME(MONTH, d),
    LEFT(DATENAME(MONTH, d), 3),
    DATEPART(QUARTER, d),
    YEAR(d),

    -- Indian FY starts April 1
    CASE WHEN MONTH(d) >= 4 THEN YEAR(d) ELSE YEAR(d)-1 END,

    -- Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar
    CASE
        WHEN MONTH(d) IN (4,5,6)    THEN 1
        WHEN MONTH(d) IN (7,8,9)    THEN 2
        WHEN MONTH(d) IN (10,11,12) THEN 3
        ELSE 4
    END,

    -- April = fiscal month 1
    CASE WHEN MONTH(d) >= 4 THEN MONTH(d)-3 ELSE MONTH(d)+9 END,

    -- e.g. 'FY24-25'
    'FY'
    + RIGHT(CAST(CASE WHEN MONTH(d)>=4 THEN YEAR(d)   ELSE YEAR(d)-1 END AS NCHAR(4)), 2)
    + '-'
    + RIGHT(CAST(CASE WHEN MONTH(d)>=4 THEN YEAR(d)+1 ELSE YEAR(d)   END AS NCHAR(4)), 2)

FROM Cal
WHERE NOT EXISTS (
    SELECT 1 FROM dw.Dim_Date x
    WHERE x.DateKey = YEAR(d)*10000 + MONTH(d)*100 + DAY(d)
);
GO


-- ---------------------------------------------------------------------
-- 4.2  Dim_Time  -  24 rows, hour level only
-- ---------------------------------------------------------------------
;WITH Hours(h) AS (
    SELECT CAST(0 AS TINYINT)
    UNION ALL
    SELECT CAST(h+1 AS TINYINT) FROM Hours WHERE h < 23
)
INSERT INTO dw.Dim_Time (TimeKey, HourLabel, HourNumber, TimePeriod, TimePeriodCode, IsPeakHour)
SELECT
    h,
    RIGHT('0' + CAST(h AS VARCHAR(2)), 2) + ':00',
    h,
    CASE
        WHEN h BETWEEN  0 AND  5 THEN 'Late Night'
        WHEN h BETWEEN  6 AND 11 THEN 'Morning'
        WHEN h BETWEEN 12 AND 17 THEN 'Afternoon'
        ELSE 'Evening'
    END,
    CASE
        WHEN h BETWEEN  0 AND  5 THEN 'LN'
        WHEN h BETWEEN  6 AND 11 THEN 'MO'
        WHEN h BETWEEN 12 AND 17 THEN 'AF'
        ELSE 'EV'
    END,
    CASE WHEN h BETWEEN 9 AND 11 OR h BETWEEN 18 AND 20 THEN 1 ELSE 0 END
FROM Hours
WHERE NOT EXISTS (SELECT 1 FROM dw.Dim_Time t WHERE t.TimeKey = h);
GO


-- ---------------------------------------------------------------------
-- 4.3  Dim_Customer  [SCD Type 2]
--
-- Flow:
--   1. Snapshot current state of each customer into a temp table,
--      one row per customer keyed to their most recent transaction.
--   2. Expire any dimension rows where the hash has changed.
--   3. Insert new rows for: (a) customers we've never seen before,
--      and (b) customers whose row we just expired in step 2.
--
-- Both the UPDATE and INSERT are inside one transaction so we never
-- end up with a customer who has no current row.
-- ---------------------------------------------------------------------
IF OBJECT_ID('tempdb..#CustomerStage') IS NOT NULL DROP TABLE #CustomerStage;

SELECT
    Customer_ID,
    Customer_Name,
    COALESCE(NULLIF(TRIM(Gender), ''), 'Unknown') AS Gender,
    CAST(Age AS TINYINT)                          AS Age,
    CASE
        WHEN Age BETWEEN 18 AND 25 THEN '18-25'
        WHEN Age BETWEEN 26 AND 35 THEN '26-35'
        WHEN Age BETWEEN 36 AND 45 THEN '36-45'
        WHEN Age BETWEEN 46 AND 60 THEN '46-60'
        ELSE '60+'
    END                                           AS AgeGroup,
    Customer_Contact,
    Customer_Email,
    CONVERT(
        NCHAR(64),
        HASHBYTES('SHA2_256',
            COALESCE(Customer_Name,    '') + '|' +
            COALESCE(NULLIF(TRIM(Gender),''),'') + '|' +
            COALESCE(CAST(Age AS VARCHAR(3)),'') + '|' +
            COALESCE(Customer_Contact, '') + '|' +
            COALESCE(Customer_Email,   '')
        ), 2
    )                                             AS RowHash
INTO #CustomerStage
FROM (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY Customer_ID
            ORDER BY Transaction_Date DESC, Transaction_Time DESC
        ) AS rn
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
    WHERE Customer_ID IS NOT NULL AND Customer_ID <> ''
) src
WHERE rn = 1;

BEGIN TRANSACTION;

    -- Expire rows where something changed
    UPDATE tgt
    SET
        RowExpiryDate = CAST(GETDATE() AS DATE),
        IsCurrent     = 0,
        UpdatedAt     = SYSUTCDATETIME()
    FROM dw.Dim_Customer tgt
    JOIN #CustomerStage  src ON src.Customer_ID = tgt.Customer_ID
                             AND tgt.IsCurrent   = 1
                             AND tgt.RowHash     <> src.RowHash;

    -- Insert new versions (new customers + just-expired rows)
    INSERT INTO dw.Dim_Customer (
        Customer_ID, Customer_Name, Gender, Age, AgeGroup,
        Customer_Contact, Customer_Email,
        RowEffectiveDate, RowExpiryDate, IsCurrent, RowHash
    )
    SELECT
        src.Customer_ID, src.Customer_Name, src.Gender, src.Age, src.AgeGroup,
        src.Customer_Contact, src.Customer_Email,
        CAST(GETDATE() AS DATE), '9999-12-31', 1, src.RowHash
    FROM #CustomerStage src
    WHERE NOT EXISTS (
        SELECT 1 FROM dw.Dim_Customer tgt
        WHERE tgt.Customer_ID = src.Customer_ID
          AND tgt.IsCurrent   = 1
    );

COMMIT TRANSACTION;
GO

DROP TABLE IF EXISTS #CustomerStage;
GO


-- ---------------------------------------------------------------------
-- 4.4  Dim_Location  (SCD Type 1)
--
-- Natural key is the full four-column combination because branches
-- can share names across cities.  IndiaRegion is refreshed on
-- WHEN MATCHED in case the mapping logic changes later.
-- ---------------------------------------------------------------------
MERGE dw.Dim_Location AS tgt
USING (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(State),               ''), 'Unknown') AS State,
        COALESCE(NULLIF(TRIM(City),                ''), 'Unknown') AS City,
        COALESCE(NULLIF(TRIM(Bank_Branch),         ''), 'Unknown') AS Bank_Branch,
        COALESCE(NULLIF(TRIM(Transaction_Location),''), 'Unknown') AS Transaction_Location,
        CASE
            WHEN TRIM(State) IN (
                'Delhi','Haryana','Himachal Pradesh','Jammu and Kashmir',
                'Jammu & Kashmir','Ladakh','Punjab','Rajasthan',
                'Uttar Pradesh','Uttarakhand','Chandigarh'
            ) THEN 'North'
            WHEN TRIM(State) IN (
                'Andhra Pradesh','Karnataka','Kerala',
                'Tamil Nadu','Telangana','Puducherry'
            ) THEN 'South'
            WHEN TRIM(State) IN ('Bihar','Jharkhand','Odisha','West Bengal')
              THEN 'East'
            WHEN TRIM(State) IN (
                'Goa','Gujarat','Maharashtra',
                'Dadra and Nagar Haveli','Daman and Diu'
            ) THEN 'West'
            WHEN TRIM(State) IN ('Chhattisgarh','Madhya Pradesh')
              THEN 'Central'
            WHEN TRIM(State) IN (
                'Arunachal Pradesh','Assam','Manipur','Meghalaya',
                'Mizoram','Nagaland','Sikkim','Tripura'
            ) THEN 'Northeast'
            ELSE 'Other'
        END AS IndiaRegion
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
    WHERE State IS NOT NULL AND City IS NOT NULL
) AS src
ON  tgt.State                = src.State
AND tgt.City                 = src.City
AND tgt.Bank_Branch          = src.Bank_Branch
AND tgt.Transaction_Location = src.Transaction_Location
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Transaction_Location, Bank_Branch, City, State, IndiaRegion)
    VALUES (src.Transaction_Location, src.Bank_Branch, src.City, src.State, src.IndiaRegion)
WHEN MATCHED AND tgt.IndiaRegion <> src.IndiaRegion THEN
    UPDATE SET tgt.IndiaRegion = src.IndiaRegion;
GO


-- ---------------------------------------------------------------------
-- 4.5  Dim_Merchant
-- ---------------------------------------------------------------------
MERGE dw.Dim_Merchant AS tgt
USING (
    SELECT DISTINCT
        Merchant_ID,
        COALESCE(NULLIF(TRIM(Merchant_Category), ''), 'Unknown') AS Merchant_Category,
        CASE
            WHEN Merchant_Category IN ('Grocery','Food & Dining','Restaurant','Supermarket','Cafe')
                THEN 'Food & Grocery'
            WHEN Merchant_Category IN ('Electronics','Retail','Online Shopping','E-commerce','Fashion')
                THEN 'Retail & E-Commerce'
            WHEN Merchant_Category IN ('Travel','Transportation','Airlines','Hotels','Rideshare')
                THEN 'Travel & Transport'
            WHEN Merchant_Category IN ('Healthcare','Medical','Pharmacy','Hospital')
                THEN 'Healthcare'
            WHEN Merchant_Category IN ('Entertainment','Gaming','Streaming','Movies','Sports')
                THEN 'Entertainment'
            WHEN Merchant_Category IN ('Utilities','Telecom','Education','Insurance','Subscription')
                THEN 'Services'
            WHEN Merchant_Category IN ('ATM','Bank','Finance','Investment','Crypto')
                THEN 'Financial Services'
            ELSE 'Other'
        END AS MerchantCategoryGroup,
        CASE
            WHEN Merchant_Category IN (
                'Online Shopping','E-commerce','Gaming',
                'Entertainment','Crypto','Finance','ATM'
            ) THEN 1 ELSE 0
        END AS IsHighRiskCategory
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
    WHERE Merchant_ID IS NOT NULL AND Merchant_ID <> ''
) AS src
ON tgt.Merchant_ID = src.Merchant_ID
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Merchant_ID, Merchant_Category, MerchantCategoryGroup, IsHighRiskCategory)
    VALUES (src.Merchant_ID, src.Merchant_Category, src.MerchantCategoryGroup, src.IsHighRiskCategory)
WHEN MATCHED AND (
    tgt.Merchant_Category     <> src.Merchant_Category     OR
    tgt.MerchantCategoryGroup <> src.MerchantCategoryGroup
) THEN
    UPDATE SET
        tgt.Merchant_Category     = src.Merchant_Category,
        tgt.MerchantCategoryGroup = src.MerchantCategoryGroup,
        tgt.IsHighRiskCategory    = src.IsHighRiskCategory;
GO


-- ---------------------------------------------------------------------
-- 4.6  Dim_TransactionType
-- ---------------------------------------------------------------------
MERGE dw.Dim_TransactionType AS tgt
USING (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(Transaction_Type), ''), 'Unknown') AS Transaction_Type,
        CASE
            WHEN Transaction_Type IN ('Withdrawal','Transfer','Payment','Purchase') THEN 'Debit'
            WHEN Transaction_Type IN ('Deposit','Refund','Credit')                  THEN 'Credit'
            ELSE 'Other'
        END AS TypeGroup,
        CASE WHEN Transaction_Type IN ('Transfer','Withdrawal') THEN 1 ELSE 0 END AS IsHighRiskType,
        CASE WHEN Transaction_Type IN ('Withdrawal','Transfer','Payment','Purchase') THEN 1 ELSE 0 END AS IsDebit,
        CASE WHEN Transaction_Type IN ('Deposit','Refund','Credit')                  THEN 1 ELSE 0 END AS IsCredit
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
) AS src
ON tgt.Transaction_Type = src.Transaction_Type
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Transaction_Type, TypeGroup, IsHighRiskType, IsDebit, IsCredit)
    VALUES (src.Transaction_Type, src.TypeGroup, src.IsHighRiskType, src.IsDebit, src.IsCredit);
GO


-- ---------------------------------------------------------------------
-- 4.7  Dim_Device
-- Transaction_Device values are already normalised by Step 5 of the
-- original script, so no extra cleanup needed here.
-- ---------------------------------------------------------------------
MERGE dw.Dim_Device AS tgt
USING (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(Device_Type),        ''), 'Unknown') AS Device_Type,
        COALESCE(NULLIF(TRIM(Transaction_Device), ''), 'Unknown') AS Transaction_Device,
        CASE
            WHEN Device_Type IN ('Mobile','Desktop','Laptop','Online','Web','App') THEN 'Digital'
            WHEN Device_Type IN ('ATM','POS')                                      THEN 'Physical'
            ELSE 'Hybrid'
        END AS DeviceChannel,
        CASE WHEN Device_Type IN ('Mobile','Desktop','Laptop','Online','Web','App') THEN 1 ELSE 0 END AS IsDigitalChannel,
        CASE WHEN Device_Type IN ('Mobile','ATM') THEN 1 ELSE 0 END AS IsHighRiskDevice
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
) AS src
ON  tgt.Device_Type        = src.Device_Type
AND tgt.Transaction_Device = src.Transaction_Device
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Device_Type, Transaction_Device, DeviceChannel, IsDigitalChannel, IsHighRiskDevice)
    VALUES (src.Device_Type, src.Transaction_Device, src.DeviceChannel, src.IsDigitalChannel, src.IsHighRiskDevice);
GO


-- ---------------------------------------------------------------------
-- 4.8  Dim_Account
-- ---------------------------------------------------------------------
MERGE dw.Dim_Account AS tgt
USING (
    SELECT DISTINCT
        COALESCE(NULLIF(TRIM(Account_Type),         ''), 'Unknown') AS Account_Type,
        COALESCE(NULLIF(TRIM(Transaction_Currency), ''), 'INR')     AS Transaction_Currency,
        CASE
            WHEN Account_Type IN ('Savings','Salary','Student') THEN 'Savings'
            WHEN Account_Type IN ('Current','Business')         THEN 'Current'
            ELSE 'Other'
        END AS AccountCategory,
        CASE WHEN Account_Type IN ('Savings','Salary','Student') THEN 1 ELSE 0 END AS IsRetailAccount
    FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
) AS src
ON  tgt.Account_Type         = src.Account_Type
AND tgt.Transaction_Currency = src.Transaction_Currency
WHEN NOT MATCHED BY TARGET THEN
    INSERT (Account_Type, Transaction_Currency, AccountCategory, IsRetailAccount)
    VALUES (src.Account_Type, src.Transaction_Currency, src.AccountCategory, src.IsRetailAccount);
GO


-- =====================================================================
-- SECTION 5  -  ETL: LOAD FACT TABLE
-- =====================================================================

-- ---------------------------------------------------------------------
-- Load Fact_BankTransaction
--
-- INNER JOINs throughout - if a row can't find its dimension key,
-- it gets excluded rather than inserting a NULL FK.  Watch the
-- row count reconciliation at the bottom; any gap between staging
-- and fact rows means a dimension lookup failed somewhere.
--
-- Risk_Score is computed here exactly as it was in Step 7 of the
-- original script (6 binary factors, 0-6 range).
--
-- The NOT EXISTS against the unique index on Transaction_ID means
-- this block is safe to re-run; already-loaded rows are skipped.
-- ---------------------------------------------------------------------
INSERT INTO dw.Fact_BankTransaction (
    Transaction_ID,
    DateKey, TimeKey,
    CustomerSK, LocationSK, MerchantSK, TransactionTypeSK, DeviceSK, AccountSK,
    Transaction_Amount, Account_Balance, Amount_to_Balance_Ratio,
    Is_Fraud, Risk_Score,
    Amount_Category, Balance_Risk_Flag,
    Transaction_Description
)
SELECT
    src.Transaction_ID,

    YEAR(src.Transaction_Date)*10000
        + MONTH(src.Transaction_Date)*100
        + DAY(src.Transaction_Date)                                   AS DateKey,

    DATEPART(HOUR, src.Transaction_Time)                              AS TimeKey,

    dc.CustomerSK,
    dl.LocationSK,
    dm.MerchantSK,
    dt.TransactionTypeSK,
    dv.DeviceSK,
    da.AccountSK,

    CAST(src.Transaction_Amount AS DECIMAL(18,2)),
    CAST(src.Account_Balance    AS DECIMAL(18,2)),
    src.Amount_to_Balance_Ratio,

    CAST(src.Is_Fraud AS TINYINT),

    -- 6-factor composite risk score, identical to original Step 7
    CAST(
        CASE WHEN src.Transaction_Hour BETWEEN 0 AND 5              THEN 1 ELSE 0 END
      + CASE WHEN src.Balance_Risk_Flag = 'High Risk'               THEN 1 ELSE 0 END
      + CASE WHEN src.Amount_Category IN ('High','Very High')       THEN 1 ELSE 0 END
      + CASE WHEN src.Transaction_Type IN ('Transfer','Withdrawal') THEN 1 ELSE 0 END
      + CASE WHEN src.Device_Type IN ('Mobile','ATM')               THEN 1 ELSE 0 END
      + CASE WHEN src.Amount_to_Balance_Ratio > 0.7                 THEN 1 ELSE 0 END
    AS TINYINT)                                                       AS Risk_Score,

    src.Amount_Category,
    src.Balance_Risk_Flag,
    CAST(src.Transaction_Description AS NVARCHAR(500))

FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean] src

JOIN dw.Dim_Customer dc
    ON  dc.Customer_ID = src.Customer_ID
    AND dc.IsCurrent   = 1

JOIN dw.Dim_Location dl
    ON  dl.State                = COALESCE(NULLIF(TRIM(src.State),               ''), 'Unknown')
    AND dl.City                 = COALESCE(NULLIF(TRIM(src.City),                ''), 'Unknown')
    AND dl.Bank_Branch          = COALESCE(NULLIF(TRIM(src.Bank_Branch),         ''), 'Unknown')
    AND dl.Transaction_Location = COALESCE(NULLIF(TRIM(src.Transaction_Location),''), 'Unknown')

JOIN dw.Dim_Merchant dm
    ON dm.Merchant_ID = src.Merchant_ID

JOIN dw.Dim_TransactionType dt
    ON dt.Transaction_Type = COALESCE(NULLIF(TRIM(src.Transaction_Type),''), 'Unknown')

JOIN dw.Dim_Device dv
    ON  dv.Device_Type        = COALESCE(NULLIF(TRIM(src.Device_Type),        ''), 'Unknown')
    AND dv.Transaction_Device = COALESCE(NULLIF(TRIM(src.Transaction_Device), ''), 'Unknown')

JOIN dw.Dim_Account da
    ON  da.Account_Type         = COALESCE(NULLIF(TRIM(src.Account_Type),         ''), 'Unknown')
    AND da.Transaction_Currency = COALESCE(NULLIF(TRIM(src.Transaction_Currency), ''), 'INR')

WHERE NOT EXISTS (
    SELECT 1 FROM dw.Fact_BankTransaction f
    WHERE f.Transaction_ID = src.Transaction_ID
);
GO

-- Row-count reconciliation - run this after every load
SELECT 'Staging'     AS Layer, COUNT(*) AS Rows FROM [BankFraudAnalysis].[dbo].[Bank_Transactions_Clean]
UNION ALL
SELECT 'Fact loaded',            COUNT(*) FROM dw.Fact_BankTransaction;
GO


-- =====================================================================
-- SECTION 6  -  ANALYSIS QUERIES
-- All original analyses preserved; dimensional joins replace the
-- inline CASE expressions that were scattered across Steps 6-7.
-- =====================================================================


-- ---------------------------------------------------------------------
-- 6.1  Executive Summary
-- ---------------------------------------------------------------------
SELECT Metric, Value
FROM (
    SELECT 1, 'Total Transactions',              CAST(COUNT(*) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 2, 'Total Fraud Cases',               CAST(SUM(Is_Fraud) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 3, 'Overall Fraud Rate %',            CAST(ROUND(SUM(Is_Fraud)*100.0/NULLIF(COUNT(*),0),2) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 4, 'Total Transaction Volume (INR)',   CAST(ROUND(SUM(Transaction_Amount),0) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 5, 'Total Fraud Amount Lost (INR)',    CAST(ROUND(SUM(CASE WHEN Is_Fraud=1 THEN Transaction_Amount ELSE 0 END),0) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 6, 'Avg Fraud Transaction (INR)',      CAST(ROUND(AVG(CASE WHEN Is_Fraud=1 THEN Transaction_Amount END),2) AS NVARCHAR(30))
    FROM dw.Fact_BankTransaction
    UNION ALL
    SELECT 7, 'Most Fraudulent Transaction Type', Transaction_Type
    FROM (
        SELECT TOP 1 tt.Transaction_Type
        FROM dw.Fact_BankTransaction f
        JOIN dw.Dim_TransactionType  tt ON tt.TransactionTypeSK = f.TransactionTypeSK
        WHERE f.Is_Fraud = 1
        GROUP BY tt.Transaction_Type ORDER BY COUNT(*) DESC
    ) A
    UNION ALL
    SELECT 8, 'Most Fraudulent Device Type',      Device_Type
    FROM (
        SELECT TOP 1 dv.Device_Type
        FROM dw.Fact_BankTransaction f
        JOIN dw.Dim_Device           dv ON dv.DeviceSK = f.DeviceSK
        WHERE f.Is_Fraud = 1
        GROUP BY dv.Device_Type ORDER BY COUNT(*) DESC
    ) B
) x (s, Metric, Value)
ORDER BY s;
GO


-- ---------------------------------------------------------------------
-- 6.2  Fraud by Transaction Type
-- TypeGroup and IsHighRiskType come from the dimension now,
-- no inline CASE needed.
-- ---------------------------------------------------------------------
SELECT
    tt.Transaction_Type,
    tt.TypeGroup,
    tt.IsHighRiskType,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct,
    ROUND(AVG(f.Transaction_Amount), 2)                 AS Avg_Amount
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_TransactionType  tt ON tt.TransactionTypeSK = f.TransactionTypeSK
GROUP BY tt.Transaction_Type, tt.TypeGroup, tt.IsHighRiskType
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.3  Fraud by Merchant Category
-- MerchantCategoryGroup gives the executive rollup that the
-- flat model couldn't provide without repeating the CASE block.
-- ---------------------------------------------------------------------
SELECT
    dm.MerchantCategoryGroup,
    dm.Merchant_Category,
    dm.IsHighRiskCategory,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct,
    ROUND(AVG(CASE WHEN f.Is_Fraud=1 THEN f.Transaction_Amount END), 2) AS Avg_Fraud_Amount
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Merchant          dm ON dm.MerchantSK = f.MerchantSK
GROUP BY dm.MerchantCategoryGroup, dm.Merchant_Category, dm.IsHighRiskCategory
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.4  Fraud by Device
-- DeviceChannel (Digital/Physical) is a new axis not in the
-- original script - useful for channel strategy reporting.
-- ---------------------------------------------------------------------
SELECT
    dv.DeviceChannel,
    dv.Device_Type,
    dv.Transaction_Device,
    dv.IsHighRiskDevice,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Device            dv ON dv.DeviceSK = f.DeviceSK
GROUP BY dv.DeviceChannel, dv.Device_Type, dv.Transaction_Device, dv.IsHighRiskDevice
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.5  Fraud by Hour of Day
-- TimePeriod label from Dim_Time replaces the four-branch CASE
-- that appeared in both Step 6 and Step 7 of the original.
-- ---------------------------------------------------------------------
SELECT
    dt.HourNumber,
    dt.HourLabel,
    dt.TimePeriod,
    dt.IsPeakHour,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Time              dt ON dt.TimeKey = f.TimeKey
GROUP BY dt.HourNumber, dt.HourLabel, dt.TimePeriod, dt.IsPeakHour
ORDER BY dt.HourNumber;
GO


-- ---------------------------------------------------------------------
-- 6.6  Fraud by Day of Week
-- ---------------------------------------------------------------------
SELECT
    dd.DayOfWeek,
    dd.DayName,
    dd.IsWeekend,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Date              dd ON dd.DateKey = f.DateKey
GROUP BY dd.DayOfWeek, dd.DayName, dd.IsWeekend
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.7  Monthly Trend  -  now with Indian fiscal period
-- FiscalYearLabel and FiscalQuarter from Dim_Date make FY-aligned
-- reporting trivial.  The original script only had calendar months.
-- ---------------------------------------------------------------------
SELECT
    dd.FiscalYearLabel,
    dd.FiscalQuarter,
    dd.FiscalMonthNumber,
    dd.CalendarYear,
    dd.MonthName,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct,
    ROUND(SUM(f.Transaction_Amount), 2)                 AS Total_Amount,
    ROUND(SUM(CASE WHEN f.Is_Fraud=1 THEN f.Transaction_Amount ELSE 0 END), 2) AS Fraud_Amount_Lost
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Date              dd ON dd.DateKey = f.DateKey
GROUP BY dd.FiscalYearLabel, dd.FiscalQuarter, dd.FiscalMonthNumber, dd.CalendarYear, dd.MonthName
ORDER BY dd.CalendarYear, dd.FiscalMonthNumber;
GO


-- ---------------------------------------------------------------------
-- 6.8  Fraud by State + Account Type  (with region rollup)
-- ---------------------------------------------------------------------
SELECT
    dl.IndiaRegion,
    dl.State,
    da.Account_Type,
    da.AccountCategory,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct,
    ROUND(SUM(f.Transaction_Amount), 2)                 AS Total_Amount
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Location          dl ON dl.LocationSK = f.LocationSK
JOIN dw.Dim_Account           da ON da.AccountSK  = f.AccountSK
GROUP BY dl.IndiaRegion, dl.State, da.Account_Type, da.AccountCategory
HAVING SUM(f.Is_Fraud) > 0
ORDER BY Fraud_Count DESC;
GO


-- ---------------------------------------------------------------------
-- 6.9  Fraud by Age Group
-- AgeGroup is stored on Dim_Customer, so this query has no CASE block.
-- ---------------------------------------------------------------------
SELECT
    dc.AgeGroup,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct,
    ROUND(AVG(f.Transaction_Amount), 2)                 AS Avg_Transaction_Amount
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Customer          dc ON dc.CustomerSK = f.CustomerSK AND dc.IsCurrent = 1
GROUP BY dc.AgeGroup
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.10  Customer Risk Segmentation
-- SCD2-aware join means the customer profile shown here reflects
-- what the customer looked like at transaction time, not today.
-- ---------------------------------------------------------------------
SELECT
    dc.Customer_ID,
    dc.Customer_Name,
    dc.AgeGroup,
    dc.Gender,
    dl.State,
    da.Account_Type,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Fraud_Count,
    ROUND(AVG(f.Transaction_Amount), 2)                 AS Avg_Transaction,
    ROUND(AVG(f.Amount_to_Balance_Ratio), 4)            AS Avg_Risk_Ratio,
    CASE
        WHEN SUM(f.Is_Fraud) >= 2                       THEN 'Critical'
        WHEN SUM(f.Is_Fraud)  = 1                       THEN 'High Risk'
        WHEN AVG(f.Amount_to_Balance_Ratio) > 0.7       THEN 'Medium Risk'
        ELSE                                                 'Low Risk'
    END AS Customer_Risk_Tier
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Customer          dc ON dc.CustomerSK = f.CustomerSK AND dc.IsCurrent = 1
JOIN dw.Dim_Location          dl ON dl.LocationSK = f.LocationSK
JOIN dw.Dim_Account           da ON da.AccountSK  = f.AccountSK
GROUP BY dc.Customer_ID, dc.Customer_Name, dc.AgeGroup, dc.Gender, dl.State, da.Account_Type
ORDER BY
    CASE
        WHEN SUM(f.Is_Fraud) >= 2                 THEN 1
        WHEN SUM(f.Is_Fraud)  = 1                 THEN 2
        WHEN AVG(f.Amount_to_Balance_Ratio) > 0.7 THEN 3
        ELSE 4
    END, Fraud_Count DESC;
GO


-- ---------------------------------------------------------------------
-- 6.11  Fraud Profile  (typical fraud pattern)
-- TimePeriod comes from Dim_Time - the four-way CASE that was in
-- both the GROUP BY and SELECT of the original query is now gone.
-- ---------------------------------------------------------------------
SELECT
    tt.Transaction_Type,
    dm.Merchant_Category,
    dv.Device_Type,
    dv.Transaction_Device,
    f.Amount_Category,
    f.Balance_Risk_Flag,
    dt.TimePeriod,
    COUNT(*)                                            AS Fraud_Count,
    ROUND(AVG(f.Transaction_Amount), 2)                 AS Avg_Fraud_Amount,
    ROUND(AVG(f.Amount_to_Balance_Ratio), 4)            AS Avg_Amount_Balance_Ratio
FROM dw.Fact_BankTransaction   f
JOIN dw.Dim_TransactionType   tt ON tt.TransactionTypeSK = f.TransactionTypeSK
JOIN dw.Dim_Merchant          dm ON dm.MerchantSK        = f.MerchantSK
JOIN dw.Dim_Device            dv ON dv.DeviceSK          = f.DeviceSK
JOIN dw.Dim_Time              dt ON dt.TimeKey            = f.TimeKey
WHERE f.Is_Fraud = 1
GROUP BY tt.Transaction_Type, dm.Merchant_Category, dv.Device_Type,
         dv.Transaction_Device, f.Amount_Category, f.Balance_Risk_Flag, dt.TimePeriod
ORDER BY Fraud_Count DESC;
GO


-- ---------------------------------------------------------------------
-- 6.12  Risk Score Validation
-- Risk_Score is a stored column now, so no sub-query needed.
-- ---------------------------------------------------------------------
SELECT
    f.Risk_Score,
    COUNT(*)                                            AS Total_Transactions,
    SUM(f.Is_Fraud)                                     AS Actual_Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2) AS Fraud_Rate_Pct
FROM dw.Fact_BankTransaction f
GROUP BY f.Risk_Score
ORDER BY f.Risk_Score DESC;
GO


-- ---------------------------------------------------------------------
-- 6.13  Region x Merchant Category Fraud Heatmap  [new]
-- This cross-tab was impossible to do cleanly in the flat model
-- because the region grouping had to be repeated inline.
-- ---------------------------------------------------------------------
SELECT
    dl.IndiaRegion,
    dm.MerchantCategoryGroup,
    COUNT(*)                                              AS Total_Transactions,
    SUM(f.Is_Fraud)                                       AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2)   AS Fraud_Rate_Pct,
    ROUND(SUM(f.Transaction_Amount)/1000000.0, 2)         AS Volume_Mn_INR
FROM dw.Fact_BankTransaction  f
JOIN dw.Dim_Location          dl ON dl.LocationSK = f.LocationSK
JOIN dw.Dim_Merchant          dm ON dm.MerchantSK = f.MerchantSK
GROUP BY dl.IndiaRegion, dm.MerchantCategoryGroup
ORDER BY Fraud_Rate_Pct DESC;
GO


-- ---------------------------------------------------------------------
-- 6.14  Fiscal Quarter Dashboard  [new]
-- Uses the FY attributes from Dim_Date.
-- High_Risk_Txn_Count is something the original script never surfaced
-- at a quarterly level.
-- ---------------------------------------------------------------------
SELECT
    dd.FiscalYearLabel,
    dd.FiscalQuarter,
    COUNT(*)                                                                   AS Total_Transactions,
    SUM(f.Is_Fraud)                                                            AS Fraud_Count,
    ROUND(SUM(f.Is_Fraud)*100.0/NULLIF(COUNT(*),0), 2)                        AS Fraud_Rate_Pct,
    ROUND(SUM(f.Transaction_Amount)/1000000.0, 2)                              AS Total_Volume_Mn_INR,
    ROUND(SUM(CASE WHEN f.Is_Fraud=1 THEN f.Transaction_Amount ELSE 0 END)/1000000.0, 2) AS Fraud_Loss_Mn_INR,
    COUNT(DISTINCT f.CustomerSK)                                               AS Unique_Customers,
    SUM(CASE WHEN f.Risk_Score >= 4 THEN 1 ELSE 0 END)                        AS High_Risk_Txn_Count
FROM dw.Fact_BankTransaction   f
JOIN dw.Dim_Date               dd ON dd.DateKey = f.DateKey
GROUP BY dd.FiscalYearLabel, dd.FiscalQuarter
ORDER BY dd.FiscalYearLabel, dd.FiscalQuarter;
GO


-- ---------------------------------------------------------------------
-- 6.15  High-Risk Transaction Drill-Through  [new]
-- Clean single-level JOIN replaces the nested sub-query approach
-- in the original Step 7 scoring query.
-- ---------------------------------------------------------------------
SELECT TOP 50
    f.Transaction_ID,
    dc.Customer_Name,
    dl.State,
    dl.City,
    f.Transaction_Amount,
    f.Account_Balance,
    f.Amount_to_Balance_Ratio,
    tt.Transaction_Type,
    dv.Device_Type,
    dt.HourLabel,
    dt.TimePeriod,
    f.Is_Fraud,
    f.Risk_Score
FROM dw.Fact_BankTransaction   f
JOIN dw.Dim_Customer          dc ON dc.CustomerSK        = f.CustomerSK AND dc.IsCurrent = 1
JOIN dw.Dim_Location          dl ON dl.LocationSK        = f.LocationSK
JOIN dw.Dim_TransactionType   tt ON tt.TransactionTypeSK = f.TransactionTypeSK
JOIN dw.Dim_Device            dv ON dv.DeviceSK          = f.DeviceSK
JOIN dw.Dim_Time              dt ON dt.TimeKey            = f.TimeKey
ORDER BY f.Risk_Score DESC, f.Transaction_Amount DESC;
GO


