#!/usr/bin/env Rscript

# Reviewer-response analysis: AICc sensitivity + breakpoint/model-selection uncertainty.
# Uses the same weighted piecewise log-linear model and candidate space as the frozen
# primary analysis (0-4 breakpoints; minimum segment length 4 years; 2000-2024).
#
# Inputs:
#   outputs/article2/article2_standardized_rates.csv
#   outputs/article2/article2_nti.csv
#
# Outputs:
#   outputs/article2/reviewer_revision/model_selection_BIC_vs_AICc.csv
#   outputs/article2/reviewer_revision/top_candidate_models_deltaBIC.csv
#   outputs/article2/reviewer_revision/breakpoint_inclusion_weights.csv
#   outputs/article2/reviewer_revision/all_candidate_models_with_AICc.csv
#   outputs/article2/reviewer_revision/model_selection_summary.txt

rates_file <- "outputs/article2/article2_standardized_rates.csv"
nti_file   <- "outputs/article2/article2_nti.csv"
out_dir    <- "outputs/article2/reviewer_revision"

MIN_SEG_YEARS <- 4
KMAX <- 4
PRIMARY_BPS <- list(
  Cerebrovascular = "2008;2020",
  Dementia = "2006;2010",
  Alzheimer = "2006;2011",
  Parkinson = "2006;2017",
  NTI = "2005;2010;2019"
)

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
  } else rhs <- "t"
  lm(as.formula(paste("log_y ~", rhs)), data=dd, weights=w)
}

aicc <- function(fit) {
  ll <- logLik(fit)
  K <- attr(ll, "df")  # lm: regression coefficients + residual variance
  n <- nobs(fit)
  a <- AIC(fit)
  if (n <= K + 1) return(Inf)
  a + (2*K*(K+1))/(n-K-1)
}

enumerate_series <- function(d, value_col, se_col, label) {
  d <- prepare_data(d, value_col, se_col)
  y0 <- min(d$year); y1 <- max(d$year)
  rows <- list(); idx <- 0
  for (k in 0:KMAX) {
    sets <- valid_knots(y0, y1, k, MIN_SEG_YEARS)
    if (!length(sets)) next
    for (knots in sets) {
      fit <- fit_with_knots(d, knots)
      idx <- idx + 1
      rows[[idx]] <- data.frame(
        series=label,
        n=nobs(fit),
        k_breakpoints=k,
        n_parameters=attr(logLik(fit), "df"),
        breakpoints=if(length(knots)) paste(knots, collapse=";") else "",
        AIC=AIC(fit),
        AICc=aicc(fit),
        BIC=BIC(fit),
        stringsAsFactors=FALSE
      )
    }
  }
  x <- do.call(rbind, rows)
  x$delta_BIC <- x$BIC - min(x$BIC)
  x$delta_AICc <- x$AICc - min(x$AICc)
  x$BIC_weight <- exp(-0.5*x$delta_BIC); x$BIC_weight <- x$BIC_weight/sum(x$BIC_weight)
  x$AICc_weight <- exp(-0.5*x$delta_AICc); x$AICc_weight <- x$AICc_weight/sum(x$AICc_weight)
  x
}

all <- list()
for (cause_name in c("Cerebrovascular","Dementia","Alzheimer","Parkinson")) {
  d <- rates[rates$geography_level=="Brazil" & rates$geography=="Brazil" & rates$sex=="Both" & rates$cause==cause_name, ]
  all[[cause_name]] <- enumerate_series(d, "asmr_per_100k", "asmr_se", cause_name)
}
dn <- nti[nti$geography_level=="Brazil" & nti$geography=="Brazil" & nti$sex=="Both", ]
all[["NTI"]] <- enumerate_series(dn, "nti", "nti_se", "NTI")
candidates <- do.call(rbind, all)

# BIC vs AICc selected models.
sel_rows <- list(); j <- 0
for (s in names(all)) {
  x <- all[[s]]
  b <- x[which.min(x$BIC),]
  a <- x[which.min(x$AICc),]
  j <- j+1
  sel_rows[[j]] <- data.frame(
    Outcome=s,
    BIC_breakpoints=b$breakpoints,
    BIC_value=b$BIC,
    AICc_breakpoints=a$breakpoints,
    AICc_value=a$AICc,
    Same_selected_configuration=(b$breakpoints==a$breakpoints),
    Frozen_primary_breakpoints=PRIMARY_BPS[[s]],
    Reproduces_frozen_primary=(b$breakpoints==PRIMARY_BPS[[s]]),
    stringsAsFactors=FALSE
  )
}
selection <- do.call(rbind, sel_rows)

# Top candidate model set: all models with delta BIC <= 6 (plus AICc deltas/weights).
top <- candidates[candidates$delta_BIC <= 6, ]
top <- top[order(top$series, top$delta_BIC),]

# Breakpoint inclusion weights: sum model weights over all candidate models containing each year.
bp_rows <- list(); z <- 0
for (s in names(all)) {
  x <- all[[s]]
  years <- seq(2004, 2020)
  for (yr in years) {
    has <- vapply(x$breakpoints, function(bp) {
      if (is.na(bp) || bp=="") return(FALSE)
      yr %in% as.integer(strsplit(bp, ";", fixed=TRUE)[[1]])
    }, logical(1))
    z <- z+1
    bp_rows[[z]] <- data.frame(
      Outcome=s,
      Breakpoint_year=yr,
      BIC_inclusion_weight=sum(x$BIC_weight[has]),
      AICc_inclusion_weight=sum(x$AICc_weight[has]),
      In_frozen_primary=yr %in% as.integer(strsplit(PRIMARY_BPS[[s]], ";", fixed=TRUE)[[1]]),
      stringsAsFactors=FALSE
    )
  }
}
bp <- do.call(rbind, bp_rows)

# For manuscript-ready compactness: retain all frozen years and any year with >=0.10 inclusion support.
bp_compact <- bp[bp$In_frozen_primary | bp$BIC_inclusion_weight >= 0.10 | bp$AICc_inclusion_weight >= 0.10, ]
bp_compact <- bp_compact[order(bp_compact$Outcome, -bp_compact$BIC_inclusion_weight),]

write.csv(selection, file.path(out_dir,"model_selection_BIC_vs_AICc.csv"), row.names=FALSE)
write.csv(top, file.path(out_dir,"top_candidate_models_deltaBIC.csv"), row.names=FALSE)
write.csv(bp_compact, file.path(out_dir,"breakpoint_inclusion_weights.csv"), row.names=FALSE)
write.csv(candidates, file.path(out_dir,"all_candidate_models_with_AICc.csv"), row.names=FALSE)

sink(file.path(out_dir,"model_selection_summary.txt"))
cat("MODEL-SELECTION SENSITIVITY AND BREAKPOINT STABILITY\n")
cat("Primary candidate space: 2000-2024; 0-4 breakpoints; minimum segment length 4 years.\n")
cat("Weighted piecewise log-linear regression; inverse-variance weights in log scale.\n\n")
cat("BIC vs AICc selected configurations:\n")
print(selection, row.names=FALSE)
cat("\nBreakpoint inclusion weights (compact):\n")
print(bp_compact, row.names=FALSE)
cat("\nCandidate count by outcome:\n")
print(table(candidates$series))
sink()

cat("Reviewer-response model-selection analysis completed.\n")
print(selection, row.names=FALSE)
cat("\nOutputs saved in:", out_dir, "\n")