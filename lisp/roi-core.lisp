(defun plist-get (plist key)
  (getf plist key))

(defun dollars (value)
  (format nil "$~,2f" (coerce value 'double-float)))

(defun safe-div (num den)
  (if (or (null den) (= den 0))
      0.0d0
      (/ (coerce num 'double-float) (coerce den 'double-float))))

(defun render-counter-list (items key-name)
  (if (null items)
      "none"
      (with-output-to-string (stream)
        (loop for item in items
              for index from 0
              do
                 (when (> index 0)
                   (write-string ", " stream))
                 (format stream "~A (~D)"
                         (or (plist-get item key-name) "unknown")
                         (or (plist-get item :count) 0))))))

(defun evidence-score (agent)
  (+ (* 2.0d0 (or (plist-get agent :active-days) 0))
     (* 1.5d0 (or (plist-get agent :project-count) 0))
     (* 1.0d0 (or (plist-get agent :work-unit-count) 0))
     (* 1.5d0 (or (plist-get (plist-get agent :git-evidence) :repo-count) 0))
     (* 0.8d0 (or (plist-get (plist-get agent :git-evidence) :commit-count) 0))
     (* 0.05d0 (or (plist-get (plist-get agent :prompt-metrics) :total-prompts) 0))
     (* 0.4d0 (or (plist-get (plist-get agent :friction-metrics) :subagent-threads) 0))))

(defun friction-score (agent)
  (+ (* 0.7d0 (or (plist-get (plist-get agent :prompt-metrics) :mega-prompt-count) 0))
     (* 1.0d0 (or (plist-get (plist-get agent :prompt-metrics) :duplicate-prompt-instances) 0))
     (* 2.0d0 (or (plist-get (plist-get agent :friction-metrics) :apply-patch-failures) 0))
     (* 1.2d0 (or (plist-get (plist-get agent :friction-metrics) :error-count) 0))
     (* 0.5d0 (or (plist-get (plist-get agent :friction-metrics) :warning-count) 0))))

(defun net-evidence-score (agent)
  (max 0.0d0 (- (evidence-score agent) (friction-score agent))))

(defun scenario-status (agent scenario)
  (let* ((seat-cost (or (plist-get scenario :monthly-cost) 0.0d0))
         (monthly-low (or (plist-get agent :monthly-cost-low) 0.0d0))
         (monthly-mid (or (plist-get agent :monthly-cost-mid) 0.0d0))
         (monthly-high (or (plist-get agent :monthly-cost-high) 0.0d0))
         (evidence (net-evidence-score agent)))
    (cond
      ((>= monthly-low seat-cost) "paying_back_from_compute")
      ((>= monthly-mid seat-cost) "paying_back_mid_estimate")
      ((and (>= monthly-high seat-cost) (> evidence 40.0d0)) "likely_paying_back")
      ((> evidence 70.0d0) "borderline_but_high_leverage")
      (t "not_paying_back_yet"))))

(defun best-scenario-ratio (agent scenario)
  (safe-div (or (plist-get agent :monthly-cost-mid) 0.0d0)
            (or (plist-get scenario :monthly-cost) 0.0d0)))

(defun emit-line (stream text)
  (write-line text stream))

(defun render-scenario-lines (stream agent scenarios)
  (dolist (scenario scenarios)
    (let* ((label (or (plist-get scenario :label) "Scenario"))
           (seat-cost (or (plist-get scenario :monthly-cost) 0.0d0))
           (status (scenario-status agent scenario))
           (ratio (best-scenario-ratio agent scenario)))
      (emit-line stream
                 (format nil "- ~A: ~A at ~,2fx midpoint monthly API-equivalent usage"
                         label status ratio))
      (emit-line stream
                 (format nil "  midpoint ~A / seat ~A | low ~A | high ~A"
                         (dollars (or (plist-get agent :monthly-cost-mid) 0.0d0))
                         (dollars seat-cost)
                         (dollars (or (plist-get agent :monthly-cost-low) 0.0d0))
                         (dollars (or (plist-get agent :monthly-cost-high) 0.0d0)))))))

(defun render-top-projects (stream agent)
  (let ((projects (plist-get agent :top-projects)))
    (if (null projects)
        (emit-line stream "- none")
        (dolist (project projects)
          (emit-line stream
                     (format nil "- ~A: ~D events, ~A, ~:D tokens"
                             (or (plist-get project :project-name) "unknown")
                             (or (plist-get project :events) 0)
                             (dollars (or (plist-get project :cost) 0.0d0))
                             (or (plist-get project :tokens) 0)))))))

(defun render-thread-samples (stream agent)
  (let ((threads (plist-get agent :sample-threads)))
    (if (null threads)
        (emit-line stream "- none")
        (dolist (thread threads)
          (emit-line stream
                     (format nil "- ~A: ~A, ~:D tokens ~@[| ~A~]"
                             (or (plist-get thread :project-name) "unknown")
                             (dollars (or (plist-get thread :usage-cost) 0.0d0))
                             (or (plist-get thread :tokens-total) 0)
                             (plist-get thread :title)))))))

(defun render-agent (stream agent scenarios)
  (let* ((name (or (plist-get agent :display-name) (plist-get agent :name)))
         (prompt-metrics (plist-get agent :prompt-metrics))
         (exec (plist-get agent :execution-metrics))
         (friction (plist-get agent :friction-metrics))
         (git (plist-get agent :git-evidence))
         (evidence (net-evidence-score agent)))
    (emit-line stream (format nil "## ~A" name))
    (emit-line stream (format nil "- Active days: ~D" (or (plist-get agent :active-days) 0)))
    (emit-line stream (format nil "- Threads: ~D" (or (plist-get agent :thread-count) 0)))
    (emit-line stream (format nil "- Projects: ~D" (or (plist-get agent :project-count) 0)))
    (emit-line stream (format nil "- Work units: ~D" (or (plist-get agent :work-unit-count) 0)))
    (emit-line stream (format nil "- Tokens observed: ~:D" (or (plist-get agent :total-tokens) 0)))
    (emit-line stream
               (format nil "- Period cost proxy: ~A midpoint (~A low / ~A high)"
                       (dollars (or (plist-get agent :cost-mid) 0.0d0))
                       (dollars (or (plist-get agent :cost-low) 0.0d0))
                       (dollars (or (plist-get agent :cost-high) 0.0d0))))
    (emit-line stream
               (format nil "- Monthlyized cost proxy: ~A midpoint (~A low / ~A high)"
                       (dollars (or (plist-get agent :monthly-cost-mid) 0.0d0))
                       (dollars (or (plist-get agent :monthly-cost-low) 0.0d0))
                       (dollars (or (plist-get agent :monthly-cost-high) 0.0d0))))
    (emit-line stream (format nil "- Cost confidence: ~A" (or (plist-get agent :cost-confidence) "unknown")))
    (emit-line stream (format nil "- Evidence score: ~,1f" evidence))
    (emit-line stream
               (format nil "- Prompt shape: ~D total, ~D mega, ~D duplicates"
                       (or (plist-get prompt-metrics :total-prompts) 0)
                       (or (plist-get prompt-metrics :mega-prompt-count) 0)
                       (or (plist-get prompt-metrics :duplicate-prompt-instances) 0)))
    (emit-line stream
               (format nil "- Git evidence: ~D repos, ~D commits"
                       (or (plist-get git :repo-count) 0)
                       (or (plist-get git :commit-count) 0)))
    (emit-line stream
               (format nil "- Execution mix: created ~D, modified ~D, commands ~D, delegated ~D"
                       (or (plist-get exec :created-file) 0)
                       (or (plist-get exec :modified-file) 0)
                       (or (plist-get exec :ran-command) 0)
                       (or (plist-get exec :delegated) 0)))
    (emit-line stream
               (format nil "- Friction: errors ~D, warnings ~D, patch failures ~D, subagent threads ~D"
                       (or (plist-get friction :error-count) 0)
                       (or (plist-get friction :warning-count) 0)
                       (or (plist-get friction :apply-patch-failures) 0)
                       (or (plist-get friction :subagent-threads) 0)))
    (emit-line stream
               (format nil "- Model mix: ~A"
                       (render-counter-list (plist-get agent :model-mix) :name)))
    (when (plist-get agent :reasoning-mix)
      (emit-line stream
                 (format nil "- Reasoning mix: ~A"
                         (render-counter-list (plist-get agent :reasoning-mix) :name))))
    (emit-line stream "")
    (emit-line stream "### Subscription sensitivity")
    (render-scenario-lines stream agent scenarios)
    (emit-line stream "")
    (emit-line stream "### Top projects")
    (render-top-projects stream agent)
    (emit-line stream "")
    (emit-line stream "### Highest-cost threads")
    (render-thread-samples stream agent)
    (emit-line stream "")
    (when (plist-get (plist-get agent :prompt-metrics) :duplicates)
      (emit-line stream "### Duplicate prompt patterns")
      (dolist (item (plist-get (plist-get agent :prompt-metrics) :duplicates))
        (emit-line stream
                   (format nil "- ~Dx ~A"
                           (or (plist-get item :count) 0)
                           (or (plist-get item :prompt) ""))))
      (emit-line stream ""))))

(defun main ()
  (let* ((args (cdr *posix-argv*))
         (input-path (first args))
         (output-path (second args)))
    (unless (and input-path output-path)
      (error "Usage: sbcl --script roi-core.lisp <input.sexp> <output.md>"))
    (with-open-file (input input-path :direction :input)
      (let* ((payload (read input nil nil))
             (window (plist-get payload :window))
             (agents (plist-get payload :agents))
             (scenarios (plist-get payload :subscription-scenarios)))
        (with-open-file (stream output-path :direction :output :if-exists :supersede :if-does-not-exist :create)
          (emit-line stream
                     (format nil "# ROI Scorecard - ~A to ~A"
                             (plist-get window :start-date)
                             (plist-get window :end-date)))
          (emit-line stream "")
          (emit-line stream
                     (format nil "This report compares monthlyized API-equivalent usage against seat-cost scenarios. It does not assume an exact subscription tier for Codex; it shows payback sensitivity instead."))
          (emit-line stream "")
          (dolist (agent agents)
            (render-agent stream agent scenarios)))))))

(main)
