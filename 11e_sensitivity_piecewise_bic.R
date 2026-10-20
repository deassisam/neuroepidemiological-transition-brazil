#!/usr/bin/env Rscript

# Article 2 — sensitivity analyses for weighted piecewise log-linear trends
# Runs on macOS with base R only.
#
# Sensitivity scenarios:
#   1) Full period 2000–2024, minimum segment = 3 years
#   2) Full period 2000–2024, minimum segment = 4 years (primary/reference)
#   3) Full period 2000–2024, minimum segment = 5 years
#   4) Pre-pandemic 2000–2019, minimum segment = 4 years
#   5) Recent-quality period 2010–2024, minimum segment = 4 years
#
# Model:
#   weighted piecewise log-linear regression
#   inverse-variance weighting in log scale
#   exhaustive search over 0–4 breakpoints
#   model selection by minimum BIC
#
# IMPORTANT FOR MANUSCRIPT:
# Report as "weighted piecewise log-linear regression with exhaustive BIC
# selection", not as NCI Joinpoint.

rates_file <- "outputs/article2/article2_standardized_rates.csv"
nti_file   <- "outputs/article2/article2_nti.csv"
out_dir    <- "outputs/article2/piecewise_bic_sensitivity"

KMAX_GLOBAL <- 4

dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)

if (!file.exists(rates_file)) stop("Missing file: ", rates_file)
if (!file.exists(nti_file)) stop("Missing file: ", nti_file)

rates <- read.csv(rates_file, stringsAsFactors=FALSE)
nti   <- read.csv(nti_file, stringsAsFactors=FALSE)

required_rate_cols <- c(
  "year","geography_level","geography","sex","cause",
  "asmr_per_100k","asmr_se"
)
required_nti_cols <- c(
  "year","geography_level","geography","sex","nti","nti_se"
)

miss_r <- setdiff(required_rate_cols, names(rates))
miss_n <- setdiff(required_nti_cols, names(nti))
if (length(miss_r)) stop("Missing rate columns: ", paste(miss_r, collapse=", "))
if (length(miss_n)) stop("Missing NTI columns: ", paste(miss_n, collapse=", "))

scenarios <- data.frame(
  scenario = c(
    "full_min3",
    "full_min4_primary",
    "full_min5",
    "prepandemic_2000_2019",
    "recent_2010_2024"
  ),
  start_year = c(2000, 2000, 2000, 2000, 2010),
  end_year   = c(2024, 2024, 2024, 2019, 2024),
  min_seg_years = c(3, 4, 5, 4, 4),
  stringsAsFactors = FALSE
)

prepare_data <- function(d, value_col, se_col, start_year, end_year) {
  d <- d[d$year >= start_year & d$year <= end_year, ]
  d <- d[order(d$year), ]

  keep <- is.finite(d[[value_col]]) & d[[value_col]] > 0 &
          is.finite(d[[se_col]]) & d[[se_col]] > 0
  d <- d[keep, ]

  expected_years <- seq(start_year, end_year)
  if (!all(expected_years %in% d$year)) {
    missing_years <- setdiff(expected_years, d$year)
    stop(
      "Missing annual observations for ", start_year, "–", end_year,
      ": ", paste(missing_years, collapse=", ")
    )
  }

  d$t <- d$year - start_year
  d$log_y <- log(d[[value_col]])
  d$se_log <- d[[se_col]] / d[[value_col]]
  d$w <- 1 / (d$se_log^2)
  d
}

valid_knots <- function(year_min, year_max, k, min_seg) {
  if (k == 0) return(list(numeric(0)))

  candidates <- seq(year_min + min_seg, year_max - min_seg, by=1)
  if (length(candidates) < k) return(list())

  cmb <- combn(candidates, k, simplify=FALSE)

  ok <- vapply(cmb, function(x) {
    bounds <- c(year_min, x, year_max)
    all(diff(bounds) >= min_seg)
  }, logical(1))

  cmb[ok]
}

fit_with_knots <- function(d, knots, start_year) {
  dd <- d

  if (length(knots)) {
    for (j in seq_along(knots)) {
      knot_t <- knots[j] - start_year
      dd[[paste0("h", j)]] <- pmax(0, dd$t - knot_t)
    }
    rhs <- paste(c("t", paste0("h", seq_along(knots))), collapse=" + ")
  } else {
    rhs <- "t"
  }

  f <- as.formula(paste("log_y ~", rhs))
  fit <- lm(f, data=dd, weights=w)
  list(fit=fit, data=dd)
}

contrast_stats <- function(fit, cvec) {
  b <- coef(fit)
  V <- vcov(fit)

  est <- sum(cvec * b)
  se <- sqrt(as.numeric(t(cvec) %*% V %*% cvec))

  crit <- qt(0.975, df=df.residual(fit))
  lo <- est - crit*se
  hi <- est + crit*se

  tval <- est / se
  p <- 2 * pt(abs(tval), df=df.residual(fit), lower.tail=FALSE)

  c(est=est, se=se, low=lo, high=hi, p=p)
}

segment_results <- function(fit, d, knots, start_year, end_year) {
  cn <- names(coef(fit))
  bounds <- c(start_year, knots, end_year)

  out <- vector("list", length(bounds)-1)

  for (s in seq_len(length(bounds)-1)) {
    cvec <- setNames(rep(0, length(cn)), cn)
    cvec["t"] <- 1

    if (length(knots)) {
      passed <- which(knots <= bounds[s] + 1e-9)
      if (length(passed)) {
        for (j in passed) {
          nm <- paste0("h", j)
          if (nm %in% cn) cvec[nm] <- 1
        }
      }
    }

    st <- contrast_stats(fit, cvec)

    out[[s]] <- data.frame(
      segment=s,
      start_year=bounds[s],
      end_year=bounds[s+1],
      APC=100*(exp(st["est"])-1),
      APC_low=100*(exp(st["low"])-1),
      APC_high=100*(exp(st["high"])-1),
      p_value=st["p"],
      stringsAsFactors=FALSE
    )
  }

  do.call(rbind, out)
}

aapc_result <- function(fit, knots, start_year, end_year, label, scenario_name) {
  cn <- names(coef(fit))
  T <- end_year - start_year

  # Average annual log-slope over the complete interval.
  # For hinge model log(y)=b0+b1*t+sum(g_j*(t-k_j)+),
  # total log change / T gives the AAPC log-slope.
  cvec <- setNames(rep(0, length(cn)), cn)
  cvec["t"] <- 1

  if (length(knots)) {
    for (j in seq_along(knots)) {
      nm <- paste0("h", j)
      if (nm %in% cn) {
        knot_t <- knots[j] - start_year
        cvec[nm] <- (T - knot_t) / T
      }
    }
  }

  st <- contrast_stats(fit, cvec)

  data.frame(
    scenario=scenario_name,
    series=label,
    start_year=start_year,
    end_year=end_year,
    AAPC=100*(exp(st["est"])-1),
    AAPC_low=100*(exp(st["low"])-1),
    AAPC_high=100*(exp(st["high"])-1),
    p_value=st["p"],
    stringsAsFactors=FALSE
  )
}

analyze_series <- function(
  d, value_col, se_col, label,
  scenario_name, start_year, end_year, min_seg_years
) {
  d <- prepare_data(d, value_col, se_col, start_year, end_year)

  # A simple feasibility cap: no point trying k values that cannot satisfy
  # the minimum segment length.
  max_feasible <- floor((end_year - start_year) / min_seg_years) - 1
  kmax <- max(0, min(KMAX_GLOBAL, max_feasible))

  candidate_rows <- list()
  fits <- list()
  idx <- 0

  for (k in 0:kmax) {
    sets <- valid_knots(start_year, end_year, k, min_seg_years)
    if (!length(sets)) next

    for (knots in sets) {
      z <- fit_with_knots(d, knots, start_year)

      idx <- idx + 1
      key <- paste(c(k, knots), collapse="_")
      fits[[key]] <- z$fit

      candidate_rows[[idx]] <- data.frame(
        scenario=scenario_name,
        series=label,
        k=k,
        BIC=BIC(z$fit),
        AIC=AIC(z$fit),
        breakpoints=if(length(knots)) paste(knots, collapse=";") else "",
        min_seg_years=min_seg_years,
        stringsAsFactors=FALSE
      )
    }
  }

  cand <- do.call(rbind, candidate_rows)

  best_i <- which.min(cand$BIC)
  best <- cand[best_i, ]

  knot_chars <- if (nchar(best$breakpoints)) {
    strsplit(best$breakpoints, ";", fixed=TRUE)[[1]]
  } else {
    character(0)
  }

  best_key <- paste(c(best$k, knot_chars), collapse="_")
  fit <- fits[[best_key]]

  knots <- if (length(knot_chars)) as.numeric(knot_chars) else numeric(0)

  apc <- segment_results(
    fit, d, knots, start_year, end_year
  )
  apc$scenario <- scenario_name
  apc$series <- label
  apc$min_seg_years <- min_seg_years
  apc <- apc[, c(
    "scenario","series","min_seg_years","segment",
    "start_year","end_year","APC","APC_low","APC_high","p_value"
  )]

  aa <- aapc_result(
    fit, knots, start_year, end_year, label, scenario_name
  )
  aa$min_seg_years <- min_seg_years
  aa <- aa[, c(
    "scenario","series","min_seg_years","start_year","end_year",
    "AAPC","AAPC_low","AAPC_high","p_value"
  )]

  best_out <- best
  best_out$start_year <- start_year
  best_out$end_year <- end_year
  best_out$n_candidates <- nrow(cand)
  best_out <- best_out[, c(
    "scenario","series","start_year","end_year","min_seg_years",
    "n_candidates","k","BIC","AIC","breakpoints"
  )]

  list(
    candidates=cand,
    best=best_out,
    apc=apc,
    aapc=aa
  )
}

series_specs <- list(
  Cerebrovascular=list(type="rate", cause="Cerebrovascular"),
  Dementia=list(type="rate", cause="Dementia"),
  Alzheimer=list(type="rate", cause="Alzheimer"),
  Parkinson=list(type="rate", cause="Parkinson"),
  NTI=list(type="nti")
)

all_results <- list()
run_index <- 0

for (si in seq_len(nrow(scenarios))) {
  sc <- scenarios[si, ]

  cat("\n\n############################################################\n")
  cat("SCENARIO:", sc$scenario, "\n")
  cat("Period:", sc$start_year, "–", sc$end_year,
      "| minimum segment:", sc$min_seg_years, "years\n")
  cat("############################################################\n")

  for (label in names(series_specs)) {
    spec <- series_specs[[label]]

    if (spec$type == "rate") {
      d <- rates[
        rates$geography_level=="Brazil" &
        rates$geography=="Brazil" &
        rates$sex=="Both" &
        rates$cause==spec$cause,
      ]
      res <- analyze_series(
        d, "asmr_per_100k", "asmr_se", label,
        sc$scenario, sc$start_year, sc$end_year, sc$min_seg_years
      )
    } else {
      d <- nti[
        nti$geography_level=="Brazil" &
        nti$geography=="Brazil" &
        nti$sex=="Both",
      ]
      res <- analyze_series(
        d, "nti", "nti_se", label,
        sc$scenario, sc$start_year, sc$end_year, sc$min_seg_years
      )
    }

    run_index <- run_index + 1
    all_results[[run_index]] <- res

    b <- res$best
    cat(
      sprintf(
        "%-16s k=%d | BIC=%0.3f | breakpoints=%s\n",
        label, b$k, b$BIC,
        ifelse(nchar(b$breakpoints), b$breakpoints, "NONE")
      )
    )
  }
}

best_all <- do.call(rbind, lapply(all_results, `[[`, "best"))
apc_all  <- do.call(rbind, lapply(all_results, `[[`, "apc"))
aapc_all <- do.call(rbind, lapply(all_results, `[[`, "aapc"))
cand_all <- do.call(rbind, lapply(all_results, `[[`, "candidates"))

write.csv(
  best_all,
  file.path(out_dir, "sensitivity_selected_models.csv"),
  row.names=FALSE
)
write.csv(
  apc_all,
  file.path(out_dir, "sensitivity_APC_by_segment.csv"),
  row.names=FALSE
)
write.csv(
  aapc_all,
  file.path(out_dir, "sensitivity_AAPC.csv"),
  row.names=FALSE
)
write.csv(
  cand_all,
  file.path(out_dir, "sensitivity_all_candidate_models.csv"),
  row.names=FALSE
)

# Compact stability matrix: selected k and breakpoint string by scenario.
stability <- best_all[, c(
  "series","scenario","start_year","end_year",
  "min_seg_years","k","BIC","breakpoints"
)]
write.csv(
  stability,
  file.path(out_dir, "sensitivity_stability_summary.csv"),
  row.names=FALSE
)

# Primary-vs-sensitivity AAPC comparison.
primary <- aapc_all[aapc_all$scenario=="full_min4_primary", ]
names(primary)[names(primary)=="AAPC"] <- "primary_AAPC"
names(primary)[names(primary)=="AAPC_low"] <- "primary_AAPC_low"
names(primary)[names(primary)=="AAPC_high"] <- "primary_AAPC_high"

comp <- merge(
  aapc_all,
  primary[, c("series","primary_AAPC","primary_AAPC_low","primary_AAPC_high")],
  by="series",
  all.x=TRUE
)
comp$AAPC_difference_from_primary <- comp$AAPC - comp$primary_AAPC

write.csv(
  comp,
  file.path(out_dir, "sensitivity_AAPC_comparison.csv"),
  row.names=FALSE
)

cat("\n\n================ SENSITIVITY: SELECTED MODELS ================\n")
print(
  best_all[, c(
    "scenario","series","start_year","end_year",
    "min_seg_years","k","BIC","breakpoints"
  )],
  row.names=FALSE
)

cat("\n================ SENSITIVITY: AAPC ================\n")
print(
  aapc_all[, c(
    "scenario","series","start_year","end_year",
    "AAPC","AAPC_low","AAPC_high","p_value"
  )],
  row.names=FALSE
)

cat("\n================ PRIMARY APC BY SEGMENT ================\n")
print(
  apc_all[apc_all$scenario=="full_min4_primary", ],
  row.names=FALSE
)

cat("\nOutputs saved in:", out_dir, "\n")
cat("Primary model remains: full_min4_primary.\n")
cat("Sensitivity scenarios should be interpreted as robustness checks, not used to re-select the primary specification.\n")