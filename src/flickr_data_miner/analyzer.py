'''
Created on Apr 19, 2010

@author: kling
'''
import cmd, sys, datetime, lxml

from lxml import etree
from lxml.cssselect import CSSSelector

class Analyzer(cmd.Cmd, object):
    '''
    No documentation available.
    '''
    CREATE_TABLES = tuple()
    TABLES = tuple()
    NAME = 'Unnamed analyzer'
    
    def __init__(self, repository):
        '''
        Constructor
        '''
        self.init()
        self.repository = repository
        cmd.Cmd.__init__(self)
        
    def init(self):
        pass
    
    
    def create_tables(self):
        for create in self.CREATE_TABLES:
            self.repository.db_conn.execute(create)
    
    def parse_file(self, id, tag, data):
        pass
    
    def initialize(self):
        self.create_tables()
        total = self.repository.total_images
        self.repository.begin_transaction()
        for i, (id, tag, data) in enumerate(self.repository.get_sites(), start=1):
            self.parse_file(id, tag, data)
            if i % 100 == 0 or i == total:
                sys.stdout.write("%i of %i images processed \r" % (i, total))
                sys.stdout.flush()
        self.repository.commit()
        print '\nDone.'

            
    def remove(self):
        for table in self.TABLES:
            self.repository.db_conn.execute('DROP TABLE ' + table) 
            
    def recreate(self):
        self.remove()
        self.initialize()
        
    def needs_init(self):
        query = "SELECT name FROM sqlite_master WHERE type='table' AND name IN (%s)" % ", ".join("%r" % s for s in self.TABLES)
        result = self.repository.db_conn.execute(query).fetchall()
        return len(result) != len(self.TABLES)
    
    def do_recreate(self, line):
        """ Recreate database. """
        
        self.recreate()
        
    def do_help(self, line):
        """ Prints the help. """
        
        if not line:
            print "\n", self.__doc__       
        super(Analyzer, self).do_help(line)
        

class BasicImageAnalyzer(Analyzer):
    """ Provides information about basic data (id, search tag, date). 
    
        DB tables:
        
        - images
            id integer PRIMARY KEY
            tag text
            uploaded date
            
    """
    
    TABLES = ("images",)
    CREATE_TABLES = ("CREATE TABLE images (id integer PRIMARY KEY, tag text, uploaded date)",)
    NAME = 'basic'
    
    def init(self):
        self._count = 0
        self.sel = CSSSelector("#thetags > div > a.Plain")
    
    def parse_file(self, id, tag, data):
        doc = etree.HTML(data)
        try:
            date = self.sel(doc)[0].text
            date = datetime.datetime.strptime(date, '%B %d, %Y')
        except IndexError:
            date = ''
        
        self.repository.db_conn.execute('INSERT INTO images (id, tag, uploaded) VALUES (?,?,?)', (id, tag, date))
        
    def do_imagecount(self, line):
        """ Get number of images in the database."""
        
        if not self._count:
            self._count = self.repository.db_conn.execute('SELECT COUNT(id) FROM images').fetchone()[0]
        print "There are %i images in the database." % self._count
        
    def do_oldest(self, line):
        """ Get ID and date of oldest uploaded photo."""
        
        info = self.repository.db_conn.execute('SELECT id, uploaded FROM images WHERE uploaded <> "" ORDER BY uploaded ASC').fetchone()      
        print "Image %s was uploaded on %s" % info
    
    def do_newest(self, line):
        """ Get ID and date of newest uploaded photo."""
        
        info = self.repository.db_conn.execute('SELECT id, uploaded FROM images WHERE uploaded <> "" ORDER BY uploaded DESC').fetchone()      
        print "Image %s was uploaded on %s" % info
    
    def do_list_tags(self, line):
        """ Get a list of the tags that have been looked for."""
        
        for tag in self.repository.db_conn.execute('SELECT DISTINCT tag FROM images ORDER BY tag ASC'):
            print '-', tag[0]
            
            

class AnalyzerCmd(cmd.Cmd, object):
    def __init__(self, repository, analyzers, completekey='Tab'):
        self._a = analyzers
        self.analyzers = dict((a.NAME, a) for a in analyzers)
        self.context = None
        cmd.Cmd.__init__(self, completekey)
        self.prompt = '> '
        self.rep = repository
        
    def preloop(self):
        not_init = [a for a in self._a if a.needs_init()]
        if not_init:
            init = ''
            while init.lower() != 'no' and init.lower() != 'yes':
                init = raw_input("%i analyzers are not yet initialized\nInitialize now? (yes [recommended]/no): " % len(not_init))
            if init.lower() == 'yes':
                total = self.rep.total_images
                for a in not_init:
                    a.create_tables()
                    self.rep.begin_transaction()
                for i, (id, tag, content) in enumerate(self.rep.get_sites(), start=1):
                    for a in not_init:
                        a.parse_file(id, tag, content)
                        sys.stdout.write("%i of %i images processed \r" % (i, total))
                        sys.stdout.flush()
                print '\nDone.'
                self.rep.commit()
            
        
    def do_exit(self, line):
        """ Exits the programm."""
        
        return True
    
    def precmd(self, line):
        if line in self.analyzers:
            line = 'sel ' + line
        return line
    
    def default(self, line):
        if self.context:
            self.context.onecmd(line)
        elif line.split()[0] in self.analyzers:
            parts = line.split()
            self.analyzers[parts[0]].onecmd(' '.join(parts[1:]))
        else:
            print "**ERROR** no such command"
    
    def do_select(self, line):
        """ Usage: select <analyzer>. Load analyzer <analyzer>.
            You can get a list which analyzers are available with "list".
        """
        
        if line in self.analyzers:
            self.context = self.analyzers[line]
            if self.context.needs_init():
                init = ''
                while init.lower() != 'no' and init.lower() != 'yes':
                    init = raw_input("The analyzer %s is not yet initialized\nInitialize now? (yes/no): " % line)
                if init.lower() == 'yes':
                    self.context.initialize()
                    self.prompt = ('(a:%s)> ' % self.context.NAME)
                else:
                    self.context = None
            else:
                self.prompt = ('(a:%s)> ' % self.context.NAME)
        else:
            print "**ERROR** Analyzer %s is not available" % line
            
    def do_list(self, line):
        """ List all available analyzers. """
        
        print '\nAvailable analyzers:\n'
        for a in self.analyzers:
            print " - %s\t\t%s" %(a.ljust(20), self.analyzers[a].__doc__.splitlines()[0])
        print ''
            
    def do_help(self, line):
        """ Prints the help. """
        
        if self.context:
            self.context.do_help(line)
        else:
            super(AnalyzerCmd, self).do_help(line)
            
    def do_return(self, line):
        """ Return from analyzer. """
        
        if self.context:
            self.context = None
            self.prompt = '> '
        