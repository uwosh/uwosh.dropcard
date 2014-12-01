"""Definition of the DropCard content type"""

from zope.interface import implements
from Products.Archetypes.Field import ComputedField
from Products.Archetypes import atapi
from Products.ATContentTypes.content import base
from Products.ATContentTypes.content import schemata
from Products.ATVocabularyManager import NamedVocabulary
import datetime
# -*- Message Factory Imported Here -*-
from uwosh.dropcard import dropcardMessageFactory as _
import xmlrpclib
import socket
from uwosh.dropcard.interfaces import IDropCard
from uwosh.dropcard.config import PROJECTNAME
from Products.CMFCore.utils import getToolByName
from Products.Archetypes.utils import DisplayList
from Products.PlonePAS.interfaces import group as igroup

webServiceBaseURL = 'http://ws.it.uwosh.edu:8080/ws'
webService = xmlrpclib.Server(webServiceBaseURL, allow_none=1)

DropCardSchema = schemata.ATContentTypeSchema.copy() + atapi.Schema((

    #-*- Your Archetypes field definitions here ... -*-
    ComputedField('title',
        searchable=1,
        expression='context._computeTitle()',
        accessor='Title',
    ),

    atapi.StringField(
        'fullname',
        storage=atapi.AnnotationStorage(),
        widget=atapi.StringWidget(
            label=_(u"Full Name"),
            description=_(u"This is your full name."),
        ),
        default_method="setDefaultFullName",
        required=True,
    ),                                                             

    atapi.StringField(
        'studentemail',
        storage=atapi.AnnotationStorage(),
        widget=atapi.StringWidget(
            label=_(u"Your UW-Oshkosh Email Address"),
            description=_(u""),
        ),
        default_method="setDefaultEmail",
        required=True,
    ),
                          
    atapi.StringField(
        'creditaudit',
        storage=atapi.AnnotationStorage(),
        widget=atapi.SelectionWidget(
            label=_(u"Credit or Audit"),
            description=_(u"Please select whether you are taking this class for credit or audit"),
        ),
        vocabulary=("Credit", "Audit",),
        required=True,
        default="Credit",
   ),

    atapi.StringField(
        'subjects',
        storage=atapi.AnnotationStorage(),
        widget=atapi.SelectionWidget(
            label=(u"Current Subject To Drop"),
            description=(u"Please pick the subject that you would like to drop."),
        ),
        required= True,
        #default_method="getWSCourseNumberNameFaculty",
        vocabulary="getWSCourseNumberNameFaculty",
    ),       

    atapi.StringField(
        'instructorID1',
        storage=atapi.AnnotationStorage(),
        widget=atapi.StringWidget(
            label=_(u"Instructor 1's ID"),
            description=_(u"This is the user ID of the instructor for the class you are dropping, and is for your information only"),
        ),
        required=True,
        searchable=True,
    ),                                                                                                                                                                                                                                                                                                                                               

    ComputedField('studentemplid',
        searchable=0,
        expression='context._computeStudentEmplid()',
        accessor='getStudentemplid',
    ),
                                                                     
    atapi.StringField(
        'comments',
        storage=atapi.AnnotationStorage(),
        widget=atapi.TextAreaWidget(
            label=_(u"Comments"),         
            description=_(u"Please fully explain why you need to drop this class."),
        ),
        required=True,
    ),                             

))

# Set storage on fields copied from ATContentTypeSchema, making sure
# they work well with the python bridge properties.

DropCardSchema['title'].storage = atapi.AnnotationStorage()
DropCardSchema['title'].required = 0
DropCardSchema['title'].widget.visible = {'edit': 'hidden', 'view': 'invisible'}

DropCardSchema['description'].storage = atapi.AnnotationStorage()
DropCardSchema['description'].widget.visible = {'edit': 'hidden', 'view': 'invisible'}

# DropCardSchema['instructorID1'].storage = atapi.AnnotationStorage()
# DropCardSchema['instructorID1'].widget.visible = {'edit': 'hidden', 'view': 'invisible'}

schemata.finalizeATCTSchema(DropCardSchema, moveDiscussion=False)


class DropCard(base.ATCTContent):
    """Implementation of Drop Card"""
    implements(IDropCard)

    meta_type = "DropCard"
    schema = DropCardSchema

    title = atapi.ATFieldProperty('title')
    description = atapi.ATFieldProperty('description')

    def setDefaultEmail(self):
        pm = getToolByName(self, "portal_membership", None)
        if pm:
            member = pm.getAuthenticatedMember()
            if member:
                return member.getProperty('email')


    def setDefaultPsterm(self):
        psterm = webService.getCurrentOrNextSemesterCX()
        return psterm

    def _huntUserFolder(self, member_id, context):
        """Find userfolder containing user in the hierarchy
           starting from context
        """
        uf = context.acl_users
        while uf is not None:
            user = uf.getUserById(member_id)
            if user is not None:
                return uf
            container = aq_parent(aq_inner(uf))
            parent = aq_parent(aq_inner(container))
            uf = getattr(parent, 'acl_users', None)
        return None


    def _huntUser(self, member_id, context):
        """Find user in the hierarchy of userfolders
           starting from context
        """
        uf = self._huntUserFolder(member_id, context)
        if uf is not None:
            return uf.getUserById(member_id)

    def setDefaultFullName(self):
        pm = getToolByName(self, "portal_membership", None)
        if pm:
            member = pm.getAuthenticatedMember()
            if member:
                return member.getProperty('fullname')

    def _computeTitle(obj):
        """Get object's title."""
        title = " ".join([obj.getFullname()])
        return title

    def _computeStudentEmplid(obj):
        """Get student's emplid via web service"""
        emplid = webService.getEmplidFromEmailAddressCX(obj.studentemail)
        return emplid

    def getWSCourseNumberNameFaculty(self):
        # if 'studentemail' == "hello":
        #     return ['COMP SCI - 331 - 001C - David Furcy - furcyd@uwosh.edu',
        #             'MATH - 172 - 001C- Joan Hart - hartj@uwosh.edu',
        #             'ENGLISH - 106 - 002C - Bobby Sue Teacher - Bobby@uwosh.edu',
        #             'History - 211 - 001C - Dwight Eisenhower - ike@uwosh.edu']
                
        try:
            return self.getEnrolledClassesFromWebService()
        except socket.error:
            try:
                return self.getEnrolledClassesFromWebService()
            except socket.error:
                logger.error('Unable to connect to: %s' % webServiceBaseURL)
                return [' ']

    def getEnrolledClassesFromWebService(self):
        please_choose = "Please Choose"
        enrolledClasses = []
        enrolledClasses.append(please_choose)
        # # emplid = self._computeStudentEmplid()
        # # strm = self.setDefaultPsterm()
        emplid = '0115341'
        strm = '0655'

        if strm == "error: no semester code found matching current date":
            logger.error('No current semester')
            return [' ']

        value = webService.getEnrolledClassesCX(emplid, strm)
        retlist = xmlrpclib.loads(value)

        try:
            for row in retlist[0]:
                subjects = row[0]
                catalognumber = row[1]
                sectionnumber = row[3] 
                courseName = row[2]
                facultyFirstName = row[5]
                facultyLastName = row[6]
                instructorID1 = row[7]
                rowString = '%s - %s - %s - %s - %s %s - %s' % (subjects, catalognumber, sectionnumber, courseName, facultyFirstName, facultyLastName, instructorID1)
                enrolledClasses.append(rowString)
        except:
            logger.error('No enrolled classes were returned by the web service')
            enrolledClasses.append('*** Error: no enrolled classes were returned by the web service ***')
        return enrolledClasses

    def getMemberEmail(self, id):
        """ Need this because portal_membership.getMemberById() is for Manager role only.
            This code is based on getMemberById but doesn't use wrapUser().
        """
        user = self._huntUser(id, self)
        if user is not None:
            email = user.getProperty('email', None)
            return email
        # otherwise just return the userid with a domain name appended
        # return id + '@uwosh.edu'


    def getRegistrarGroupMemberEmails(self):
        """ Need this because portal_groups.getGroupMembers() is protected.
        """
        return [self.getMemberEmail(m) for m in self.getGroupMembers('Registrar')]


    def getGroupMembers(self, group_id):
        members = set()
        introspectors = self._getGroupIntrospectors()
        for iid, introspector in introspectors:
            members.update(introspector.getGroupMembers(group_id))
        return list(members)


    def _getGroupIntrospectors(self):
        return self._getPlugins().listPlugins(
            igroup.IGroupIntrospection
            )


    def _getPlugins(self):
        return self.acl_users.plugins

    def _computeTitle(obj):
        """Get object's title."""
        title = " ".join([obj.fullname or '?', obj.subjects or '?',])
        return title

    # -*- Your ATSchema to Python Property Bridges Here ... -*-
    subjects = atapi.ATFieldProperty('subjects')

    #classnumber = atapi.ATFieldProperty('classnumber')

    studentid = atapi.ATFieldProperty('studentid')

    instructorID1 = atapi.ATFieldProperty('instructorID1')

    catalognumber = atapi.ATFieldProperty('catalognumber')

    # lastname = atapi.ATFieldProperty('lastname')

    fullname = atapi.ATFieldProperty('fullname')

    comments = atapi.ATFieldProperty('comments')

    creditaudit = atapi.ATFieldProperty('creditaudit')

    studentemail = atapi.ATFieldProperty('studentemail')

def objectSetTitle(obj, event):
    title = " ".join([obj.fullname or '?', obj.subjects or '?',])
    if obj.Title() != title:
        obj.Title(title)
        obj.reindexObject()


def objectInitialized(obj, event):
    objectSetTitle(obj, event)
   

def objectEdited(obj, event):
    objectSetTitle(obj, event)

atapi.registerType(DropCard, PROJECTNAME)
