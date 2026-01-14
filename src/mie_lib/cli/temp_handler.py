def handle_update_everything(args):
    """
    Handle update-everything command.
    Runs the full daily incremental pipeline: Raw -> Features -> Analytics -> Report
    """
    # Validate tickers resolve from YAML
    tickers = _load_yaml_tickers()
    if not tickers:
        print("update-everything ERROR: no tickers resolved from config/tickers.yml")
        sys.exit(2)
    
    if getattr(args, "validate_only", False):
        print("Validation Mode: Checks passed. (Health check should be run separately via script)")
        sys.exit(0)
        
    target_stage = getattr(args, "stage", None)
    dry_run = getattr(args, "dry_run", False)
    
    def run_stage(name, cmd_list):
        if target_stage and target_stage.lower() != name.lower():
            return # Skip if not matching filter
        
        if dry_run:
            print(f"[DRY-RUN] Would run stage '{name}': {' '.join(cmd_list)}")
            return

        # Execute
        try:
            _run(cmd_list)
        except Exception as e:
            print(f"ERROR in stage '{name}': {e}")
            raise e

    # --- JOB TRACKING ---
    from mie_lib.services.job_tracker import JobTracker
    tracker = JobTracker()
    tracker.start_job("Daily Update", total_steps=11)
    # --------------------

    py = sys.executable
    mie = os.fspath(Path(__file__).resolve())
    
    try:
        # RAW incremental
        if not target_stage or target_stage == "raw":
            tracker.update_progress(1, "Updating Raw Data...")
            get_audit_logger().start_job("Daily Update Pipeline") # START GLOBAL JOB
            get_audit_logger().start_stage("Update Raw Data")
            run_stage("raw", [py, mie, "update-raw"])
        
        # FEATURES incremental + CSV
        if not target_stage or target_stage == "features":
            tracker.update_progress(2, "Building Features...")
            get_audit_logger().start_stage("Update Features")
            run_stage("features", [py, mie, "build-features", "--mode", "update", "--lookback", "90", "--csv"])

        # SMA STACK ANALYTICS
        if not target_stage or target_stage == "analytics":
            tracker.update_progress(3, "Calculating SMA Stack...")
            print("Starting SMA/EMA Stack Trend Analysis...")
            get_audit_logger().start_stage("SMA/EMA Stack")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc SMA Stack")
                else:
                    from mie_lib.analytics.sma_stack import calculate_and_save_sma_stack
                    calculate_and_save_sma_stack()
                    print("SMA/EMA Stack analysis completed successfully.")
                    get_audit_logger().update_stage("SMA/EMA Stack", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating SMA/EMA Stack: {e}")
                get_audit_logger().update_stage("SMA/EMA Stack", "FAILED", {"error": str(e)})
            
            # ADX/DMI ANALYTICS
            tracker.update_progress(4, "Calculating ADX/DMI...")
            print("Starting ADX/DMI Analysis...")
            get_audit_logger().start_stage("ADX/DMI")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc ADX")
                else:
                    from mie_lib.analytics.adx_dmi import calculate_and_save_adx
                    calculate_and_save_adx()
                    print("ADX/DMI analysis completed successfully.")
                    get_audit_logger().update_stage("ADX/DMI", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating ADX/DMI: {e}")
                get_audit_logger().update_stage("ADX/DMI", "FAILED", {"error": str(e)})

            # ICHIMOKU ANALYTICS
            get_audit_logger().start_stage("Ichimoku")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc Ichimoku")
                else:
                    from mie_lib.analytics.ichimoku import calculate_and_save_ichimoku
                    calculate_and_save_ichimoku()
                    print("Ichimoku analysis completed successfully.")
                    get_audit_logger().update_stage("Ichimoku", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating Ichimoku: {e}")
                get_audit_logger().update_stage("Ichimoku", "FAILED", {"error": str(e)})

            # PSAR ANALYTICS
            tracker.update_progress(4.5, "Calculating Parabolic SAR...")
            print("Starting PSAR Analysis...")
            get_audit_logger().start_stage("PSAR")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc PSAR")
                else:
                    from mie_lib.analytics.psar import calculate_and_save_psar
                    calculate_and_save_psar()
                    print("PSAR analysis completed successfully.")
                    get_audit_logger().update_stage("PSAR", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating PSAR: {e}")
                get_audit_logger().update_stage("PSAR", "FAILED", {"error": str(e)})

        # SEASONALITY incremental
        if not target_stage or target_stage == "seasonality":
            tracker.update_progress(5, "Updating Seasonality...")
            get_audit_logger().start_stage("Seasonality")
            run_stage("seasonality", [py, mie, "update-seasonality"])
            get_audit_logger().update_stage("Seasonality", "COMPLETED", {})
        
        # MARKOV grid refresh
        if not target_stage or target_stage == "markov":
            tracker.update_progress(6, "Building Markov Models...")
            get_audit_logger().start_stage("Markov Grid")
            run_stage("markov", [py, mie, "build-markov-grid",
                "--state-modes", "binary,tri",
                "--thresholds", ",".join(str(i) for i in range(0,151,5)),
                "--windows", "1Y,2Y,5Y,10Y,20Y,MAX",
                "--orders", "1,2,3,4"])  # uses default tickers resolver
            get_audit_logger().update_stage("Markov Grid", "COMPLETED", {})
            
        # HMM grid refresh
        if not target_stage or target_stage == "hmm":
            tracker.update_progress(7, "Building HMM Grid...")
            get_audit_logger().start_stage("HMM Grid")
            run_stage("hmm", [py, mie, "build-hmm-grid", "--tickers", "@config", "--windows", "5,10,MAX", "--states", "2,3"])
            get_audit_logger().update_stage("HMM Grid", "COMPLETED", {})
        
        # EXPECTED MOVES (Reliability)
        if not target_stage or target_stage == "expected_moves":
            tracker.update_progress(8, "Calculating Expected Moves...")
            get_audit_logger().start_stage("Expected Moves")
            run_stage("expected_moves", [py, mie, "update-expected-moves", "--ticker", "@config", "--lookback", "5"])
            run_stage("expected_moves", [py, mie, "build-expected-moves-snapshots", "--tickers", "@config"])
            get_audit_logger().update_stage("Expected Moves", "COMPLETED", {})

        # HMM SNAPSHOTS (UI)
        if not target_stage or target_stage == "snapshots":
            tracker.update_progress(9, "Generating Snapshots...")
            get_audit_logger().start_stage("Snapshots")
            run_stage("snapshots", [py, mie, "build-hmm-snapshots", "--tickers", "@config"])
            get_audit_logger().update_stage("Snapshots", "COMPLETED", {})
        
        # HMM BACKTEST (Specific for SPY)
        if not target_stage or target_stage == "backtest":
            tracker.update_progress(9.5, "Running HMM Backtests...")
            get_audit_logger().start_stage("HMM Backtest SPY")
            try:
                run_stage("backtest", [py, mie, "backtest-hmm", "--ticker", "SPY"])
                get_audit_logger().update_stage("HMM Backtest SPY", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: backtest-hmm failed: {e}")
                get_audit_logger().update_stage("HMM Backtest SPY", "FAILED", {"error": str(e)})
        
        # GEX (Best Effort)
        if not target_stage or target_stage == "gex":
            try:
                tracker.update_progress(10, "Updating Gamma Exposure...")
                get_audit_logger().start_stage("GEX")
                # Fetch Options Snapshot First (Polygon)
                run_stage("gex", [py, mie, "fetch-options-snapshot", "--tickers", "@config"])
                # Then Build GEX
                run_stage("gex", [py, mie, "build-gex-daily", "--date", "today", "--tickers", "@config"])
                
                # --- NEW: Archive GEX ---
                try:
                    run_stage("gex_archive", [py, mie, "archive-gex-daily", "--tickers", "SPY"])
                except Exception as ex:
                    print(f"WARN: archive-gex-daily failed: {ex}")
                    # Don't fail the whole job for archiving
                # ------------------------
                
                get_audit_logger().update_stage("GEX", "COMPLETED", {})
            except SystemExit:
                print("WARN: build-gex-daily failed (likely missing flat files), continuing...")
                get_audit_logger().update_stage("GEX", "SKIPPED", {"reason": "Missing Flat Files"})
            except Exception as e:
                print(f"WARN: build-gex-daily failed: {e}")
                get_audit_logger().update_stage("GEX", "FAILED", {"error": str(e)})

        # TSMOM DAILY UPDATE
        if not target_stage or target_stage == "tsmom":
            try:
                tracker.update_progress(11, "Updating TSMOM & GAF...")
                get_audit_logger().start_stage("TSMOM")
                run_stage("tsmom", [py, mie, "build-tsmom-daily", "--tickers", "@config"])
                get_audit_logger().update_stage("TSMOM", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: build-tsmom-daily failed: {e}")
                get_audit_logger().update_stage("TSMOM", "FAILED", {"error": str(e)})

        if not target_stage or target_stage == "gaf":
            try:
                get_audit_logger().start_stage("GAF")
                run_stage("gaf", [py, mie, "build-gaf-daily", "--ticker", "@config"])
                get_audit_logger().update_stage("GAF", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: build-gaf-daily failed: {e}")
                get_audit_logger().update_stage("GAF", "FAILED", {"error": str(e)})

        # ECONOMIC PIPELINE (FRED + COI/LAG/LEI MODELS)
        if not target_stage or target_stage == "economic":
            try:
                tracker.update_progress(11.2, "Updating Economic Models...")
                get_audit_logger().start_stage("Economic Pipeline")
                run_stage("economic", [py, mie, "update-economic"])
                get_audit_logger().update_stage("Economic Pipeline", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: update-economic failed: {e}")
                get_audit_logger().update_stage("Economic Pipeline", "FAILED", {"error": str(e)})

        # AI CONTEXT + REPORT
        if not target_stage or target_stage == "report":
            try:
                tracker.update_progress(11.5, "Generating AI Analysis...")
                get_audit_logger().start_stage("AI Context Generation")
                run_stage("report", [py, mie, "generate-ai-context", "--ticker", "SPY"])
                
                # New Stage for Report
                run_stage("report", [py, mie, "generate-ai-report", "--ticker", "SPY"])
            except Exception as e:
                print(f"WARN: AI Generation failed: {e}")
                get_audit_logger().update_stage("AI Context Generation", "FAILED", {"error": str(e)})

        if getattr(args, "snapshots", False):
            get_audit_logger().start_stage("Publish Analytics Data")
            # Logic for snapshots if needed, or assumed done by previous steps
            get_audit_logger().update_stage("Publish Analytics Data", "COMPLETED", {})

        tracker.finish_job("completed", "Daily Update Complete")
        get_audit_logger().finish_job("COMPLETED")
        print("✅ Done.")
        sys.exit(0)
        
    except Exception as e:
        tracker.finish_job("failed", f"Job Failed: {str(e)}")
        get_audit_logger().finish_job("FAILED", f"Job Failed: {str(e)}")
        print(f"❌ Job Failed: {e}")
        sys.exit(1)
