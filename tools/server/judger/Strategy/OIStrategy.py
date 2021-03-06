import shutil
import traceback
import os
import stat

from Strategy import Strategy


class OIStrategy(Strategy):
    def __init__(self, socket, connection, console):
        Strategy.__init__(self, socket, connection, console)

    def _consume(self, data):
        try:
            for tid, test in enumerate(self._conf['tests']):
                self._emit_case('COMPILING')
                compile_path = self._gen_tmp_dir('compile')
                self._save_code(data, compile_path)
                self._copy_includes(compile_path)
                self._copy_at_stage(0, test, compile_path, -1)
                executable = []
                language = data[self._conf['main'] + 'lang']
                if language == 'C++':
                    compile_cmd = test['compiler']['C++']
                    for cmd in compile_cmd:
                        if not self._compile(cmd, language, compile_path):
                            return
                    executable.append('code')
                elif language == 'Java':
                    compile_cmd = test['compiler']['Java']
                    for cmd in compile_cmd:
                        if not self._compile(cmd, language, compile_path):
                            return
                    executable.append('Main.class')
                elif language == "Git":
                    compile_cmd = test['compiler']['Git']
                    if len(self._conf['files']) > 1:
                        raise Exception("Have more than one url in Git judge.") 
                    for code in self._conf['files']:
                        if 'name' not in self._conf['files'][code]:
                            self._buffer.setdefault('verdict', 6)
                        git_repo = data[code].strip()
                    git_dir = self.get_git_dir(git_repo)
                    if git_dir == False:
                        return
                    if not self._gitclone('--unsafe /usr/bin/git clone ' + git_repo, work_path=compile_path, tl=120000):
                        return
                    # git.Git(compile_path).clone(git_repo)
                    compile_path = compile_path + '/' + git_dir
                    for cmd in compile_cmd:
                        if not self._compile(cmd, language, compile_path):
                            return
                    executable.append('code')
                    executable.append('bin/')
                elif language == 'plain':
                    executable.append('plain.txt')
                else:
                    self._buffer.setdefault('compile', 'Compilation failure: unknown programming language')
                    self._buffer.setdefault('verdict', 10)
                    return

            used_time = 0
            used_memo = 0
            case_id = 0
            verdict = 0
            score = 0.0

            for tid, test in enumerate(self._conf['tests']):
                for index in xrange(test['repeat']):
                    case_id += 1
                    self._emit_case(case_id)
                    self._console('Running on test {} repeated {} times caseid={}'.format(tid + 1, index + 1, case_id))
                    run_path = self._gen_tmp_dir(case_id)
                    for path in executable:
                        full_path = compile_path + '/' + path
                        if os.path.exists(full_path):
                            if (os.path.isdir(full_path)):
                                shutil.copytree(full_path, run_path + '/' + path)
                            else:
                                shutil.copy(full_path, run_path + '/')
                    self._copy_at_stage(index + 1, test, run_path, 0)
                    runcmd = test['command'][language]
                    runcmd = runcmd.replace('[$INDEX]', str(index + 1))
                    run_type = test.get('type', None)
                    result = self._execute(runcmd=runcmd, rtype = run_type,
                                           work_path=run_path,
                                           sin=test['input'],
                                           sout=test['output'],
                                           serr='error.txt',
                                           tl=test['limit'][language]['time'],
                                           ml=test['limit'][language]['memory'])
                    self._buffer.setdefault('input-' + str(case_id), self._readfile(run_path + '/' + test['input']))
                    self._buffer.setdefault('output-' + str(case_id), self._readfile(run_path + '/' + test['output']))
                    self._copy_at_stage(index + 1, test, run_path, 1)
                    self._buffer.setdefault('stdout-' + str(case_id), self._readfile(run_path + '/' + test['stdout']))
                    runcode = int(result[0])
                    self._buffer.setdefault('verdict-' + str(case_id), runcode)
                    self._buffer.setdefault('score-' + str(case_id), '/'.join(["0", str(test['score'])]))
                    self._buffer.setdefault('time-' + str(case_id), int(result[2].split(' ')[0]))
                    self._buffer.setdefault('memo-' + str(case_id), int(result[2].split(' ')[1]))
                    self._buffer.setdefault('exit-' + str(case_id), int(result[2].split(' ')[2]))
                    used_time = max(used_time, int(result[2].split(' ')[0]))
                    used_memo = max(used_memo, int(result[2].split(' ')[1]))
                    if runcode == 2:
                        self._buffer.setdefault('report-' + str(case_id), result[2])
                    if runcode != 0:
                        self._buffer.setdefault('verdict', runcode)
                        continue
                    self._move_judger(case_id, test['judger'], run_path)
                    os.chmod(run_path + '/__judger', stat.S_IXUSR)
                    open(run_path + '/score.in', 'w').write(str(test['score']))
                    result = self._execute(runcmd='--unsafe ./__judger ' + test['input'] + ' ' + test['stdout'] + ' ' + test['output'] + ' score.in score.out',
                                           sout="__judge.out",
                                           work_path=run_path,
                                           tl=10,
                                           ml=1048576)
                    exitcode = int(result[2].split(' ')[2])
                    judge_run_code = int(result[0])
                    if judge_run_code == 1:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: Judger time limit exceeded')
                        return
                    elif judge_run_code == 2:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: Judger crashed("{}")'.format(result[1].rstrip('\n')))
                        return
                    elif judge_run_code == 3:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: Judger output limit exceeded')
                        return
                    elif judge_run_code == 4:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: Judger memory limit exceeded')
                        return
                    elif judge_run_code == 5:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: dangerous judgement')
                        return
                    elif judge_run_code == 6:
                        self._buffer = {}
                        self._buffer.update({'verdict': 6})
                        self._buffer.setdefault('report', 'Judge failure: Cannot execute the judger')
                        return
                    elif exitcode != 0:
                        if verdict == 0:
                            verdict = 7
                        self._buffer.update({'verdict-' + str(case_id): 7})
                        self._buffer.update({'report-' + str(case_id): self._readfile(run_path + '/__judge.out')})
                    elif run_type != None and self.kitValgrindXMLHasError(run_path + '/' + test['valgrind']):
                        self._buffer.update({'verdict': 13})
                        self._buffer.update({'verdict-' + str(case_id): 13})
                        self._buffer.update({'report-' + str(case_id): self._readfile(run_path + '/' + test['valgrind'], 5000)})
                    else:
                        self._buffer.pop('input-' + str(case_id))
                        self._buffer.pop('output-' + str(case_id))
                        self._buffer.pop('stdout-' + str(case_id))
                        self._buffer.update({'report-' + str(case_id): self._readfile(run_path + '/__judge.out')})
                    case_score = float(open(run_path + '/score.out', 'r').read())
                    self._buffer.update({'score-' + str(case_id): '/'.join([str(case_score), str(test['score'])])})
                    score += float(open(run_path + '/score.out', 'r').read())
            self._buffer.setdefault('score', score)
            self._buffer.setdefault('verdict', verdict)
            if verdict == 0:
                self._buffer.setdefault('time', used_time)
                self._buffer.setdefault('memo', used_memo)
        except Exception as e:
            self._buffer = {'verdict': 6, 'report': 'invalid problem configuration.'}
            self._console(e.__doc__)
            self._console(e.message)
            traceback.print_exc()
