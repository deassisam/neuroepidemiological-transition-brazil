#!/usr/bin/env Rscript

# Article 2 — constrained weighted piecewise log-linear trend analysis
# Deterministic exhaustive BIC search with a minimum segment length.
# Runs fully on macOS with base R (no extra packages required).
#
# IMPORTANT FOR MANUSCRIPT:
# Describe as "weighted piecewise log-linear regression with exhaustive BIC
# selection", NOT as NCI Joinpoint.
#
# Primary defaults:
# - annual data, 2000–2024
# - 0–4 breakpoints
# - minimum 4 calendar years between breakpoints and endpoints
# - inverse-variance weights on log(rate) or log(NTI)
# - APC and AAPC with 95% CIs from linear contrasts of the fitted model

rates_file <- "outputs/article2/article2_standardized_rates.csv"
nti_file   <- "outputs/article2/article2_nti.csv"
out_dir    <- "outputs/article2/piecewise_bic_mac"

MIN_SEG_YEARS <- 4
KMAX <- 4

dir.create(out_dir, recursive=TRUE, showWarnings=FALSE)

if (!file.exists(rates_file)) stop("Missing file: ", rates_file)
if (!file.exists(nti_file)) stop("Missing file: ", nti_file)

rates <- read.csv(rates_file, stringsAsFactors=FALSE)
nti   <- read.csv(nti_file, stringsAsFactors=FALSE)

prepare_data <- function(d, value_col, se_col) {
  d <- d[order(d$year), ]
  keep <- is.finite(d[[value_col]]) & d[[value_col]] > 0 &
          is.finite(d[[se_col]]) & d[[se_col]] > 0
  d <- d[keep, ]
  if (nrow(d) < 10) stop("Too few usable annual observations.")
  d$t <- d$year - min(d$year)
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

fit_with_knots <- function(d, knots) {
  dd <- d
  if (length(knots)) {
    for (j in seq_along(knots)) {
      knot_t <- knots[j] - min(d$year)
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

contrast_stats <- function(fit, cvec, df_resid) {
  b <- coef(fit)
  V <- vcov(fit)
  est <- sum(cvec * b)
  se <- sqrt(as.numeric(t(cvec) %*% V %*% cvec))
  crit <- qt(0.975, df=df_resid)
  lo <- est - crit*se
  hi <- est + crit*se
  tval <- est/se
  p <- 2*pt(abs(tval), df=df_resid, lower.tail=FALSE)
  c(est=est, se=se, low=lo, high=hi, p=p)
}

segment_results <- function(fit, d, knots) {
  cn <- names(coef(fit))
  year0 <- min(d$year)
  bounds <- c(year0, knots, max(d$year))

  out <- vector("list", length(bounds)-1)

  for (s in seq_len(length(bounds)-1)) {
    # Slope = beta_t + all hinge coefficients for knots already passed.
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

    st <- contrast_stats(fit, cvec, df.residual(fit))
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

aapc_result <- function(fit, d, label) {
  cn <- names(coef(fit))
  year0 <- min(d$year)
  year1 <- max(d$year)
  T <- year1-year0

  make_x <- function(year) {
    tt <- year-year0
    x <- setNames(rep(0, length(cn)), cn)
    if ("(Intercept)" %in% cn) x["(Intercept)"] <- 1
    if ("t" %in% cn) x["t"] <- tt
    hinge_names <- grep("^h[0-9]+$", cn, value=TRUE)
    if (length(hinge_names)) {
      for (nm in hinge_names) {
        j <- as.integer(sub("^h","",nm))
        # recover knot from hinge definition in model frame:
        # h_j = max(0, t-knot_t), so knot_t is first t where h_j > 0 minus h_j
        hv <- model.frame(fit)[[nm]]
        tv <- model.frame(fit)[["t"]]
        pos <- which(hv > 0)[1]
        if (is.na(pos)) {
          knot_t <- max(tv)
        } else {
          knot_t <- tv[pos] - hv[pos]
        }
        x[nm] <- max(0, tt-knot_t)
      }
    }
    x
  }

  x0 <- make_x(year0)
  x1 <- make_x(year1)
  cvec <- (x1-x0)/T
  st <- contrast_stats(fit, cvec, df.residual(fit))

  data.frame(
    series=label,
    start_year=year0,
    end_year=year1,
    AAPC=100*(exp(st["est"])-1),
    AAPC_low=100*(exp(st["low"])-1),
    AAPC_high=100*(exp(st["high"])-1),
    p_value=st["p"],
    stringsAsFactors=FALSE
  )
}

analyze_series <- function(d, value_col, se_col, label) {
  d <- prepare_data(d, value_col, se_col)
  y0 <- min(d$year); y1 <- max(d$year)

  candidates_rows <- list()
  fits <- list()
  idx <- 0

  for (k in 0:KMAX) {
    sets <- valid_knots(y0, y1, k, MIN_SEG_YEARS)
    if (!length(sets)) next

    for (knots in sets) {
      z <- fit_with_knots(d, knots)
      idx <- idx+1
      key <- paste(c(k, knots), collapse="_")
      fits[[key]] <- z$fit
      candidates_rows[[idx]] <- data.frame(
        series=label,
        k=k,
        BIC=BIC(z$fit),
        AIC=AIC(z$fit),
        breakpoints=if(length(knots)) paste(knots, collapse=";") else "",
        stringsAsFactors=FALSE
      )
    }
  }

  cand <- do.call(rbind, candidates_rows)
  best_i <- which.min(cand$BIC)
  best <- cand[best_i, ]
  best_key <- paste(c(best$k,
                      if(nchar(best$breakpoints)) strsplit(best$breakpoints,";",fixed=TRUE)[[1]] else NULL),
                    collapse="_")
  fit <- fits[[best_key]]
  knots <- if(nchar(best$breakpoints)) as.numeric(strsplit(best$breakpoints,";",fixed=TRUE)[[1]]) else numeric(0)

  apc <- segment_results(fit, d, knots)
  apc$series <- label
  apc <- apc[, c("series","segment","start_year","end_year",
                 "APC","APC_low","APC_high","p_value")]

  aa <- aapc_result(fit, d, label)

  pred <- data.frame(
    series=label,
    year=d$year,
    observed=d[[value_col]],
    fitted=exp(predict(fit, newdata=model.frame(fit)))
  )

  cat("\n============================================================\n")
  cat(label, "\n")
  cat("============================================================\n")
  cat("Candidate models fitted:", nrow(cand), "\n")
  cat("Selected k:", best$k, "\n")
  cat("Selected breakpoints:",
      if(nchar(best$breakpoints)) best$breakpoints else "NONE", "\n")
  cat("BIC:", round(best$BIC, 5), "\n")

  list(candidates=cand, best=best, fit=fit, apc=apc, aapc=aa, pred=pred)
}

results <- list()

for (cause_name in c("Cerebrovascular","Dementia","Alzheimer","Parkinson")) {
  d <- rates[
    rates$geography_level=="Brazil" &
    rates$geography=="Brazil" &
    rates$sex=="Both" &
    rates$cause==cause_name,
  ]
  results[[cause_name]] <- analyze_series(
    d, "asmr_per_100k", "asmr_se", cause_name
  )
}

dnti <- nti[
  nti$geography_level=="Brazil" &
  nti$geography=="Brazil" &
  nti$sex=="Both",
]
results[["NTI"]] <- analyze_series(
  dnti, "nti", "nti_se", "NTI"
)

best_all <- do.call(rbind, lapply(results, `[[`, "best"))
apc_all <- do.call(rbind, lapply(results, `[[`, "apc"))
aapc_all <- do.call(rbind, lapply(results, `[[`, "aapc"))
pred_all <- do.call(rbind, lapply(results, `[[`, "pred"))
cand_all <- do.call(rbind, lapply(results, `[[`, "candidates"))

write.csv(best_all, file.path(out_dir, "selected_models.csv"), row.names=FALSE)
write.csv(apc_all, file.path(out_dir, "APC_by_segment.csv"), row.names=FALSE)
write.csv(aapc_all, file.path(out_dir, "AAPC_2000_2024.csv"), row.names=FALSE)
write.csv(pred_all, file.path(out_dir, "fitted_values.csv"), row.names=FALSE)
write.csv(cand_all, file.path(out_dir, "all_candidate_models.csv"), row.names=FALSE)

cat("\n\n================ CONSTRAINED BIC SUMMARY ================\n")
print(best_all[, c("series","k","BIC","breakpoints")], row.names=FALSE)

cat("\n================ APC BY SEGMENT ================\n")
print(apc_all, row.names=FALSE)

cat("\n================ AAPC 2000–2024 ================\n")
print(aapc_all, row.names=FALSE)

cat("\nMethod: weighted piecewise log-linear regression; exhaustive BIC search;",
    "minimum segment length =", MIN_SEG_YEARS, "years; Kmax =", KMAX, "\n")
cat("Saved in:", out_dir, "\n")