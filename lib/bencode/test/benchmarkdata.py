#!/usr/bin/env python
# encoding: utf-8
"""
    Benchmark data for the bcode module
"""

__author__ = "Tom Lazar (tom@tomster.org)"
__version__ = "$Revision: 0.1 $"
__date__ = "$Date: 2007/07/29 $"
__copyright__ = "Copyright (c) 2007 Tom Lazar"
__license__ = "Python"

from bencode import bencode

PARROT_SKETCH = """A customer enters a pet shop. 

     Mr. Praline: 'Ello, I wish to register a complaint. 

     (The owner does not respond.) 

     Mr. Praline: 'Ello, Miss? 

     Owner: What do you mean "miss"? 

     Mr. Praline: I'm sorry, I have a cold. I wish to make a complaint! 

     Owner: We're closin' for lunch. 

     Mr. Praline: Never mind that, my lad. I wish to complain about this parrot what I purchased not half an hour ago from this very boutique. 

     Owner: Oh yes, the, uh, the Norwegian Blue...What's,uh...What's wrong with it? 

     Mr. Praline: I'll tell you what's wrong with it, my lad. 'E's dead, that's what's wrong with it! 

     Owner: No, no, 'e's uh,...he's resting. 

     Mr. Praline: Look, matey, I know a dead parrot when I see one, and I'm looking at one right now. 

     Owner: No no he's not dead, he's, he's restin'! Remarkable bird, the Norwegian Blue, idn'it, ay? Beautiful plumage! 

     Mr. Praline: The plumage don't enter into it. It's stone dead. 

     Owner: Nononono, no, no! 'E's resting! 

     Mr. Praline: All right then, if he's restin', I'll wake him up! (shouting at the cage) 'Ello, Mister Polly Parrot! I've got a lovely fresh cuttle fish for you if you 
     show... 

     (owner hits the cage) 

     Owner: There, he moved! 

     Mr. Praline: No, he didn't, that was you hitting the cage! 

     Owner: I never!! 

     Mr. Praline: Yes, you did! 

     Owner: I never, never did anything... 

     Mr. Praline: (yelling and hitting the cage repeatedly) 'ELLO POLLY!!!!! Testing! Testing! Testing! Testing! This is your nine o'clock alarm call! 

     (Takes parrot out of the cage and thumps its head on the counter. Throws it up in the air and watches it plummet to the floor.) 

     Mr. Praline: Now that's what I call a dead parrot. 

     Owner: No, no.....No, 'e's stunned! 

     Mr. Praline: STUNNED?!? 

     Owner: Yeah! You stunned him, just as he was wakin' up! Norwegian Blues stun easily, major. 

     Mr. Praline: Um...now look...now look, mate, I've definitely 'ad enough of this. That parrot is definitely deceased, and when I purchased it not 'alf an hour 
     ago, you assured me that its total lack of movement was due to it bein' tired and shagged out following a prolonged squawk. 

     Owner: Well, he's...he's, ah...probably pining for the fjords. 

     Mr. Praline: PININ' for the FJORDS?!?!?!? What kind of talk is that?, look, why did he fall flat on his back the moment I got 'im home? 

     Owner: The Norwegian Blue prefers keepin' on it's back! Remarkable bird, id'nit, squire? Lovely plumage! 

     Mr. Praline: Look, I took the liberty of examining that parrot when I got it home, and I discovered the only reason that it had been sitting on its perch in the 
     first place was that it had been NAILED there. 

     (pause) 

     Owner: Well, o'course it was nailed there! If I hadn't nailed that bird down, it would have nuzzled up to those bars, bent 'em apart with its beak, and 
     VOOM! Feeweeweewee! 

     Mr. Praline: "VOOM"?!? Mate, this bird wouldn't "voom" if you put four million volts through it! 'E's bleedin' demised! 

     Owner: No no! 'E's pining! 

     Mr. Praline: 'E's not pinin'! 'E's passed on! This parrot is no more! He has ceased to be! 'E's expired and gone to meet 'is maker! 'E's a stiff! Bereft of life, 'e 
     rests in peace! If you hadn't nailed 'im to the perch 'e'd be pushing up the daisies! 'Is metabolic processes are now 'istory! 'E's off the twig! 'E's kicked the 
     bucket, 'e's shuffled off 'is mortal coil, run down the curtain and joined the bleedin' choir invisibile!! THIS IS AN EX-PARROT!! 

     (pause) 

     Owner: Well, I'd better replace it, then. (he takes a quick peek behind the counter) Sorry squire, I've had a look 'round the back of the shop, and uh, 
     we're right out of parrots. 

     Mr. Praline: I see. I see, I get the picture. 

     Owner: I got a slug. 

     (pause) 

     Mr. Praline: Pray, does it talk? 

     Owner: Nnnnot really. 

     Mr. Praline: WELL IT'S HARDLY A BLOODY REPLACEMENT, IS IT?!!???!!? 

     Owner: N-no, I guess not. (gets ashamed, looks at his feet) 

     Mr. Praline: Well. 

     (pause) 

     Owner: (quietly) D'you.... d'you want to come back to my place? 

     Mr. Praline: (looks around) Yeah, all right, sure.
"""

sampleValues = [
    643332,
    PARROT_SKETCH,
    {
        'title' : 'Parrot Sketch',
        'year' : 1963,
        'lyrics' : PARROT_SKETCH,
        'writers' : ['Micheal Palin', 'John Cleese']
    },
    range(1, 9999)
]

sampleEncodedValues = [bencode(item) for item in sampleValues]
